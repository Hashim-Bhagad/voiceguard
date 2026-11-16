"""AASIST-L model adapter.

This project deliberately uses only the official ClovaAI AASIST-L architecture.
Run ``scripts/bootstrap_aasist.py`` once to place the pinned upstream repository
under ``training/third_party/aasist`` before training or export.

The architecture block below is a verbatim copy of ``model_config`` from upstream
``config/AASIST-L.conf``. Keeping it here (and validating against it) means a
config typo fails fast instead of silently producing a model whose state dict no
longer matches the released ``AASIST-L.pth``.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

TRAINING_ROOT = Path(__file__).resolve().parents[1]

AASIST_L_MODEL_CONFIG: dict[str, Any] = {
    "architecture": "AASIST",
    "nb_samp": 64600,
    "first_conv": 128,
    "filts": [70, [1, 32], [32, 32], [32, 24], [24, 24]],
    "gat_dims": [24, 32],
    "pool_ratios": [0.4, 0.5, 0.7, 0.5],
    "temperatures": [2.0, 2.0, 100.0, 100.0],
}

# Published parameter count for AASIST-L; a mismatch means the config drifted.
AASIST_L_PARAM_COUNT = 85_306


def resolve_upstream_dir(upstream_dir: str | Path) -> Path:
    """Accept absolute paths, or paths relative to the caller or to training/."""
    candidate = Path(upstream_dir)
    for option in (candidate, TRAINING_ROOT / candidate):
        resolved = option.resolve()
        if (resolved / "models" / "AASIST.py").is_file():
            return resolved
    raise FileNotFoundError(
        f"Official AASIST source not found at {candidate!r} (also tried "
        f"{TRAINING_ROOT / candidate}). Run 'python scripts/bootstrap_aasist.py' from training/."
    )


def _load_upstream_model(upstream_dir: str | Path) -> type[nn.Module]:
    root = resolve_upstream_dir(upstream_dir)
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    module = importlib.import_module("models.AASIST")
    return module.Model


def _validate_config(config: dict[str, Any]) -> None:
    if config.get("architecture") != "AASIST":
        raise ValueError(
            f"architecture must be 'AASIST' (the upstream class name), got {config.get('architecture')!r}"
        )
    missing = set(AASIST_L_MODEL_CONFIG) - set(config)
    if missing:
        raise ValueError(f"model.architecture is missing keys: {sorted(missing)}")
    differing = {
        key: (AASIST_L_MODEL_CONFIG[key], config[key])
        for key in AASIST_L_MODEL_CONFIG
        if config[key] != AASIST_L_MODEL_CONFIG[key]
    }
    if differing:
        detail = ", ".join(f"{k}: expected {v[0]!r}, got {v[1]!r}" for k, v in differing.items())
        raise ValueError(
            "model.architecture does not match the official AASIST-L config, so the released "
            f"AASIST-L.pth will not load: {detail}"
        )


class AASISTL(nn.Module):
    """Thin, explicit adapter around the pinned official AASIST implementation."""

    def __init__(self, upstream_dir: str | Path, model_config: dict[str, Any] | None = None):
        super().__init__()
        config = {**AASIST_L_MODEL_CONFIG, **(model_config or {})}
        _validate_config(config)
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
        """Load an upstream AASIST-L checkpoint, tolerating common wrappers."""
        blob = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        state = blob.get("model", blob.get("state_dict", blob)) if isinstance(blob, dict) else blob
        if not isinstance(state, dict):
            raise ValueError("Pretrained checkpoint does not contain a state dictionary")
        state = {key.removeprefix("module."): value for key, value in state.items()}
        missing, unexpected = self.net.load_state_dict(state, strict=False)
        return list(missing), list(unexpected)

    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


class SpoofLogitExport(nn.Module):
    """Exports the spoof-vs-bonafide log-odds expected by the backend.

    Positive output means more spoof-like. A single scalar keeps the ONNX contract
    stable regardless of how the two-class head is arranged internally.
    """

    def __init__(self, model: AASISTL):
        super().__init__()
        self.model = model

    def forward(self, waveform: torch.Tensor) -> torch.Tensor:
        logits = self.model(waveform)
        return logits[:, 1] - logits[:, 0]


MODEL_TYPES = ("aasist_l", "xlsr_aasist")


def model_type(cfg: dict[str, Any]) -> str:
    kind = str(cfg["model"].get("type", "aasist_l")).lower()
    if kind not in MODEL_TYPES:
        raise ValueError(f"model.type must be one of {MODEL_TYPES}, got {kind!r}")
    return kind


def build_model(cfg: dict[str, Any]) -> nn.Module:
    """Build the configured model. ``model.type`` defaults to ``aasist_l``."""
    if model_type(cfg) == "xlsr_aasist":
        from src.ssl_model import build_xlsr_model  # lazy: needs transformers

        return build_xlsr_model(cfg)

    model_cfg = cfg["model"]
    model = AASISTL(
        upstream_dir=model_cfg["upstream_dir"],
        model_config=model_cfg.get("architecture"),
    )
    actual = model.num_parameters()
    if actual != AASIST_L_PARAM_COUNT:
        raise RuntimeError(
            f"Built model has {actual} parameters but AASIST-L has {AASIST_L_PARAM_COUNT}. "
            "The upstream revision or the architecture config changed."
        )
    return model
