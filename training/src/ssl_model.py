"""XLS-R + AASIST-style graph back-end for multilingual spoof detection.

Why this model exists next to AASIST-L
--------------------------------------
AASIST-L learns from raw waveforms with 85K parameters. That is ideal on a
phone, but it has to discover every speech feature from the anti-spoofing data
alone, and models of that family generalise poorly to unseen synthesisers and to
real-world audio. A self-supervised speech encoder already knows what natural
speech looks like. ``facebook/wav2vec2-xls-r-300m`` was pre-trained on 436K hours
in 128 languages, including Hindi, Marathi, Tamil and Bengali, so it directly
targets VoiceGuard's multilingual setting. This is the recipe of Tak et al.,
"Automatic speaker verification spoofing and deepfake detection using wav2vec
2.0 and data augmentation" (Odyssey 2022).

Partial fine-tuning
-------------------
Only the top ``finetune_top_layers`` of XLS-R's 24 transformer layers are
trained, plus a learned softmax weighting over all 25 hidden states and the
whole back-end. The CNN feature encoder and the lower transformer layers stay
frozen. Because nothing below the first trainable layer requires a gradient,
autograd records no graph there: the frozen part costs one forward pass and no
activation memory, which is what keeps a T4 run to hours instead of days.

Back-end
--------
The graph-attention readout reuses the official AASIST layers
(GraphAttentionLayer, HtrgGraphAttentionLayer, GraphPool) from the pinned
upstream checkout. The 2-D residual encoder is re-implemented here, because the
upstream block (a) pools time by 3 in every block, which would collapse XLS-R's
~201 frames to zero after six blocks, and (b) overwrites its own ``bn1`` output,
so that layer never trains. The ONNX contract is unchanged:
``waveform float32[batch, 64600]`` in, two logits ``[bonafide, spoof]`` out.
"""
from __future__ import annotations

import importlib
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from src.model import _load_upstream_model, resolve_upstream_dir

DEFAULT_SSL = {
    "pretrained": "facebook/wav2vec2-xls-r-300m",
    "finetune_top_layers": 8,
    "layer_weighting": True,
}
DEFAULT_BACKEND = {
    "proj_dim": 128,
    "channels": [32, 32, 64, 64],
    "time_pool": [2, 2, 1, 1],
    "gat_dims": [64, 32],
    "pool_ratios": [0.5, 0.5, 0.5],
    "temperatures": [2.0, 2.0, 100.0],
}


def _upstream_graph_layers(upstream_dir: str):
    _load_upstream_model(upstream_dir)  # puts the pinned checkout on sys.path
    module = importlib.import_module("models.AASIST")
    return module.GraphAttentionLayer, module.HtrgGraphAttentionLayer, module.GraphPool


class ResBlock2d(nn.Module):
    """Pre-activation residual block that pools only along time."""

    def __init__(self, in_ch: int, out_ch: int, time_pool: int, first: bool = False):
        super().__init__()
        self.pre = nn.Identity() if first else nn.Sequential(nn.BatchNorm2d(in_ch), nn.SELU())
        self.conv1 = nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(out_ch)
        self.conv2 = nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1)
        self.skip = nn.Conv2d(in_ch, out_ch, kernel_size=1) if in_ch != out_ch else nn.Identity()
        self.pool = nn.MaxPool2d((1, time_pool)) if time_pool > 1 else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv1(self.pre(x))
        out = self.conv2(F.selu(self.bn2(out)))
        return self.pool(out + self.skip(x))


class XLSRAASIST(nn.Module):
    """XLS-R front-end, partially fine-tuned, with an AASIST graph back-end."""

    def __init__(self, upstream_dir: str, window_samples: int, ssl_cfg: dict | None = None,
                 backend_cfg: dict | None = None, ssl_model: nn.Module | None = None):
        super().__init__()
        self.ssl_cfg = {**DEFAULT_SSL, **(ssl_cfg or {})}
        self.backend_cfg = {**DEFAULT_BACKEND, **(backend_cfg or {})}
        self.window_samples = int(window_samples)

        if ssl_model is None:
            from transformers import Wav2Vec2Model

            # SpecAugment masking and LayerDrop are pre-training regularisers;
            # leaving them on makes the frozen layers non-deterministic.
            ssl_model = Wav2Vec2Model.from_pretrained(
                self.ssl_cfg["pretrained"], mask_time_prob=0.0, mask_feature_prob=0.0,
                layerdrop=0.0, apply_spec_augment=False,
            )
        self.ssl = ssl_model
        n_layers = int(self.ssl.config.num_hidden_layers)
        hidden = int(self.ssl.config.hidden_size)
        self.n_layers = n_layers
        self._freeze(int(self.ssl_cfg["finetune_top_layers"]))
        self.layer_weights = (
            nn.Parameter(torch.zeros(n_layers + 1)) if self.ssl_cfg["layer_weighting"] else None
        )

        b = self.backend_cfg
        gat_layer, htrg_layer, graph_pool = _upstream_graph_layers(upstream_dir)
        self.proj = nn.Linear(hidden, b["proj_dim"])
        self.first_bn = nn.BatchNorm2d(1)
        blocks, in_ch = [], 1
        for i, (ch, tp) in enumerate(zip(b["channels"], b["time_pool"])):
            blocks.append(ResBlock2d(in_ch, ch, tp, first=i == 0))
            in_ch = ch
        self.encoder = nn.Sequential(*blocks)
        c = in_ch
        self.attention = nn.Sequential(
            nn.Conv2d(c, 2 * c, kernel_size=1), nn.BatchNorm2d(2 * c), nn.SELU(),
            nn.Conv2d(2 * c, c, kernel_size=1),
        )
        n_spec = b["proj_dim"] // 3  # after the 3x3 max-pool below
        self.pos_S = nn.Parameter(torch.randn(1, n_spec, c) * 0.02)
        g0, g1 = b["gat_dims"]
        t_s, t_t, t_h = b["temperatures"]
        self.master1 = nn.Parameter(torch.randn(1, 1, g0))
        self.master2 = nn.Parameter(torch.randn(1, 1, g0))
        self.gat_S = gat_layer(c, g0, temperature=t_s)
        self.gat_T = gat_layer(c, g0, temperature=t_t)
        self.htrg11 = htrg_layer(g0, g1, temperature=t_h)
        self.htrg12 = htrg_layer(g1, g1, temperature=t_h)
        self.htrg21 = htrg_layer(g0, g1, temperature=t_h)
        self.htrg22 = htrg_layer(g1, g1, temperature=t_h)
        r_s, r_t, r_h = b["pool_ratios"]
        self.pool_S = graph_pool(r_s, g0, 0.3)
        self.pool_T = graph_pool(r_t, g0, 0.3)
        self.pool_hS1 = graph_pool(r_h, g1, 0.3)
        self.pool_hT1 = graph_pool(r_h, g1, 0.3)
        self.pool_hS2 = graph_pool(r_h, g1, 0.3)
        self.pool_hT2 = graph_pool(r_h, g1, 0.3)
        self.drop_way = nn.Dropout(0.2)
        self.drop = nn.Dropout(0.5)
        self.out_layer = nn.Linear(5 * g1, 2)

    # ----------------------------------------------------------------- freezing
    def _freeze(self, top_layers: int) -> None:
        if not 0 <= top_layers <= self.n_layers:
            raise ValueError(f"finetune_top_layers must be in [0, {self.n_layers}], got {top_layers}")
        for p in self.ssl.parameters():
            p.requires_grad = False
        first_trainable = self.n_layers - top_layers
        for i, layer in enumerate(self.ssl.encoder.layers):
            if i >= first_trainable:
                for p in layer.parameters():
                    p.requires_grad = True
        if top_layers > 0:
            # The encoder's closing LayerNorm sits above the last layer.
            for p in self.ssl.encoder.layer_norm.parameters():
                p.requires_grad = True
        self.trainable_ssl_layers = list(range(first_trainable, self.n_layers))

    def train(self, mode: bool = True):
        super().train(mode)
        # Frozen layers stay in eval mode: no dropout noise in features that
        # cannot adapt to it. Trainable layers follow the requested mode.
        self.ssl.eval()
        if mode:
            for i in self.trainable_ssl_layers:
                self.ssl.encoder.layers[i].train()
        return self

    # ------------------------------------------------------------------ forward
    def ssl_features(self, waveform: torch.Tensor) -> torch.Tensor:
        # XLS-R expects zero-mean, unit-variance input (its feature extractor's
        # do_normalize). Done here so the ONNX graph and the backend need nothing.
        mean = waveform.mean(dim=1, keepdim=True)
        std = waveform.var(dim=1, keepdim=True, unbiased=False).add(1e-7).sqrt()
        x = (waveform - mean) / std
        if self.layer_weights is None:
            return self.ssl(x).last_hidden_state
        hidden = self.ssl(x, output_hidden_states=True).hidden_states  # n_layers + 1
        weights = torch.softmax(self.layer_weights, dim=0)
        return (torch.stack(hidden, dim=0) * weights[:, None, None, None]).sum(dim=0)

    def forward(self, waveform: torch.Tensor, freq_aug: bool = False) -> torch.Tensor:
        """Return two unnormalised logits ordered [bonafide, spoof]."""
        del freq_aug  # AASIST-L's sinc-filter masking has no analogue here
        if waveform.ndim != 2:
            raise ValueError(f"Expected [batch, samples] waveform, got {tuple(waveform.shape)}")
        feats = self.proj(self.ssl_features(waveform))        # (B, T, proj)
        x = feats.transpose(1, 2).unsqueeze(1)                 # (B, 1, proj, T)
        x = F.selu(self.first_bn(F.max_pool2d(x, (3, 3))))     # (B, 1, proj/3, T/3)
        x = self.encoder(x)                                    # (B, C, F, T')
        w = self.attention(x)
        e_S = (x * torch.softmax(w, dim=-1)).sum(dim=-1).transpose(1, 2) + self.pos_S  # (B, F, C)
        e_T = (x * torch.softmax(w, dim=-2)).sum(dim=-2).transpose(1, 2)               # (B, T', C)

        out_S = self.pool_S(self.gat_S(e_S))
        out_T = self.pool_T(self.gat_T(e_T))
        batch = waveform.size(0)
        master1 = self.master1.expand(batch, -1, -1)
        master2 = self.master2.expand(batch, -1, -1)

        out_T1, out_S1, master1 = self.htrg11(out_T, out_S, master=master1)
        out_S1, out_T1 = self.pool_hS1(out_S1), self.pool_hT1(out_T1)
        t_aug, s_aug, m_aug = self.htrg12(out_T1, out_S1, master=master1)
        out_T1, out_S1, master1 = out_T1 + t_aug, out_S1 + s_aug, master1 + m_aug

        out_T2, out_S2, master2 = self.htrg21(out_T, out_S, master=master2)
        out_S2, out_T2 = self.pool_hS2(out_S2), self.pool_hT2(out_T2)
        t_aug, s_aug, m_aug = self.htrg22(out_T2, out_S2, master=master2)
        out_T2, out_S2, master2 = out_T2 + t_aug, out_S2 + s_aug, master2 + m_aug

        out_T = torch.max(self.drop_way(out_T1), self.drop_way(out_T2))
        out_S = torch.max(self.drop_way(out_S1), self.drop_way(out_S2))
        master = torch.max(self.drop_way(master1), self.drop_way(master2))
        hidden = torch.cat([
            out_T.abs().max(dim=1).values, out_T.mean(dim=1),
            out_S.abs().max(dim=1).values, out_S.mean(dim=1),
            master.squeeze(1),
        ], dim=1)
        return self.out_layer(self.drop(hidden))

    # -------------------------------------------------------------- utilities
    def optimizer_groups(self, train_cfg: dict[str, Any]) -> list[dict]:
        """Smaller learning rate for the pre-trained layers than for the new head."""
        ssl_params = [p for p in self.ssl.parameters() if p.requires_grad]
        ssl_ids = {id(p) for p in ssl_params}
        head = [p for p in self.parameters() if p.requires_grad and id(p) not in ssl_ids]
        groups = [{"params": head, "lr": float(train_cfg["lr"])}]
        if ssl_params:
            groups.append({"params": ssl_params, "lr": float(train_cfg.get("ssl_lr", 1e-5))})
        return groups

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def num_trainable(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def describe(self) -> str:
        first = self.trainable_ssl_layers[0] if self.trainable_ssl_layers else None
        frozen = f"layers 0-{first - 1}" if first else "none"
        return (f"XLS-R {self.n_layers} layers: training {len(self.trainable_ssl_layers)} "
                f"(top), frozen CNN + {frozen}; {self.num_trainable():,} of "
                f"{self.num_parameters():,} parameters trainable")


def build_xlsr_model(cfg: dict[str, Any], ssl_model: nn.Module | None = None) -> XLSRAASIST:
    model_cfg = cfg["model"]
    resolve_upstream_dir(model_cfg["upstream_dir"])  # fail early with a clear message
    return XLSRAASIST(
        upstream_dir=model_cfg["upstream_dir"],
        window_samples=model_cfg["window_samples"],
        ssl_cfg=model_cfg.get("ssl"),
        backend_cfg=model_cfg.get("backend"),
        ssl_model=ssl_model,
    )
