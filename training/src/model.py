"""AASIST-L model adapter.

This project deliberately uses only the official ClovaAI AASIST-L architecture.
Run ``scripts/bootstrap_aasist.py`` once in Colab to place the pinned upstream
repository under ``training/third_party/aasist`` before training or export.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn


AASIST_L_MODEL_CONFIG = {
    "architecture": "AASIST",
    "nb_samp": 64600,
    "first_conv": 128,
    "filts": [70, [1, 32], [32, 32], [32, 24], [24, 24]],
    "gat_dims": [24, 32],
    "pool_ratios": [0.4, 0.5, 0.7, 0.5],
    "temperatures": [2.0, 2.0, 100.0, 100.0],
}


def _load_upstream_model(upstream_dir: str | Path) -> type[nn.Module]:
    root = Path(upstream_dir).resolve()
    if not (root / "models" / "AASIST.py").is_file():
        raise FileNotFoundError(
            f"Official AASIST source is missing at {root}. Run "
            "python scripts/bootstrap_aasist.py from training/."
        )
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    module = importlib.import_module("models.AASIST")
    return module.Model


class AASISTL(nn.Module):
    """Thin, explicit adapter around the pinned official AASIST implementation."""

    def __init__(self, upstream_dir: str | Path, model_config: dict[str, Any] | None = None):
        super().__init__()
        config = dict(AASIST_L_MODEL_CONFIG)
        if model_config:
            config.update(model_config)
        if config != {**AASIST_L_MODEL_CONFIG, **(model_config or {})}:
            raise ValueError("Invalid AASIST-L model configuration")
        self.window_samples = int(config["nb_samp"])
        self.net = _load_upstream_model(upstream_dir)(config)

    def forward(self, waveform: torch.Tensor, freq_aug: bool = False) -> torch.Tensor:
        """Return two unnormalised logits ordered [bonafide, spoof]."""
        if waveform.ndim != 2:
            raise ValueError(f"Expected [batch, samples] waveform, got {tuple(waveform.shape)}")
        result = self.net(waveform, Freq_aug=freq_aug)
        logits = result[1] if isinstance(result, tuple) else result
        if logits.ndim != 2 or logits.shape[1] != 2:
            raise RuntimeError(f"AASIST-L must return [batch, 2] logits, got {tuple(logits.shape)}")
        return logits

    def load_pretrained(self, checkpoint_path: str | Path) -> tuple[list[str], list[str]]:
        """Load an upstream AASIST-L checkpoint while handling common wrappers."""
        blob = torch.load(checkpoint_path, map_location="cpu")
        state = blob.get("model", blob.get("state_dict", blob)) if isinstance(blob, dict) else blob
        if not isinstance(state, dict):
            raise ValueError("Pretrained checkpoint does not contain a state dictionary")
        state = {key.removeprefix("module."): value for key, value in state.items()}
        missing, unexpected = self.net.load_state_dict(state, strict=False)
        return list(missing), list(unexpected)


class SpoofLogitExport(nn.Module):
    """Exports the spoof-vs-bonafide log-odds expected by the backend."""

    def __init__(self, model: AASISTL):
        super().__init__()
        self.model = model

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        logits = self.model(waveform)
        return logits[:, 1] - logits[:, 0]


def build_model(cfg: dict[str, Any]) -> AASISTL:
    model_cfg = cfg["model"]
    return AASISTL(
        upstream_dir=model_cfg["upstream_dir"],
        model_config=model_cfg.get("architecture"),
    )
