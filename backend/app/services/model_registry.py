"""Lazy CPU ONNX AASIST-L registry with a mock fallback for UI development."""
import hashlib
import os
from pathlib import Path

import numpy as np

from app.core.config import get_settings

AASIST_L_SAMPLES = 64600
_loaded: dict[str, object] = {}
_load_error: dict[str, str] = {}


def backend_name() -> str:
    return get_settings().model_backend


def model_version() -> str:
    """Honest version string.

    This must never claim the neural model when the neural model is not actually
    running. ``score_spoof`` falls back to a development heuristic if the ONNX
    file is missing or fails to load, and a response labelled
    'aasist-l-indic-v0.1' while carrying heuristic numbers is indistinguishable
    from a real detection to anyone downstream.
    """
    settings = get_settings()
    if settings.model_backend != "aasist-l-onnx":
        return "mock-v0.1"
    if _try_onnx(settings.aasist_l_onnx) is None:
        return "heuristic-fallback-v0.1"
    return Path(settings.aasist_l_onnx).stem or "aasist-l-indic-v0.1"


def _try_onnx(path: str):
    if path in _loaded:
        return _loaded[path]
    if path in _load_error:
        return None
    if not os.path.exists(path):
        _load_error[path] = f"file not found: {os.path.abspath(path)}"
        return None
    try:
        import onnxruntime as ort

        session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        _loaded[path] = session
        return session
    except Exception as exc:  # noqa: BLE001
        _load_error[path] = f"{type(exc).__name__}: {exc}"
        return None


def model_status() -> dict:
    """Provable, inspectable statement of what will actually score the audio.

    Exposed on /api/v1/health so a caller can verify the neural model is live
    rather than inferring it from a config flag.
    """
    settings = get_settings()
    path = Path(settings.aasist_l_onnx)
    status: dict[str, object] = {
        "configured_backend": settings.model_backend,
        "model_path": str(path),
        "model_path_absolute": str(path.resolve()) if path.exists() else None,
        "model_file_exists": path.is_file(),
        "model_sha256": None,
        "onnx_session_loaded": False,
        "inference_path": "heuristic",
        "load_error": None,
        "reported_model_ver": model_version(),
    }
    if settings.model_backend != "aasist-l-onnx":
        status["inference_path"] = "mock"
        return status

    if path.is_file():
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        status["model_sha256"] = digest.hexdigest()
        status["model_bytes"] = path.stat().st_size

    session = _try_onnx(settings.aasist_l_onnx)
    if session is not None:
        status["onnx_session_loaded"] = True
        status["inference_path"] = "aasist-l-onnx"
        status["providers"] = list(session.get_providers())
        status["inputs"] = [
            {"name": i.name, "shape": [str(d) for d in i.shape]} for i in session.get_inputs()
        ]
        status["outputs"] = [
            {"name": o.name, "shape": [str(d) for d in o.shape]} for o in session.get_outputs()
        ]
    else:
        status["load_error"] = _load_error.get(settings.aasist_l_onnx, "unknown")
    return status


def _repeat_pad(waveform: np.ndarray, samples: int = AASIST_L_SAMPLES) -> np.ndarray:
    """Tile a short signal up to the model window.

    Must match training (training/src/dataset.py:repeat_pad) and the official
    AASIST pad(). Zero padding would leave a silent tail whose length correlates
    with clip duration, which the model never saw during training -- a
    train/serve mismatch that biases scores on short uploads.
    """
    if len(waveform) >= samples:
        return waveform[:samples]
    repeats = int(np.ceil(samples / max(1, len(waveform))))
    return np.tile(waveform, repeats)[:samples].astype(np.float32, copy=False)


def _aasist_windows(waveform_16k: np.ndarray, max_windows: int = 8) -> np.ndarray:
    """Return [n, 64600] windows covering the clip.

    Training and eval score one fixed 4.04 s window. A real upload can be much
    longer, so we tile the clip into up to ``max_windows`` evenly spaced windows
    and let the caller aggregate. One centre window on a 30 s file would ignore
    87% of the audio.
    """
    waveform = np.ascontiguousarray(
        np.asarray(waveform_16k, dtype=np.float32).reshape(-1)
    )
    if len(waveform) <= AASIST_L_SAMPLES:
        return _repeat_pad(waveform)[None, :]

    stride = AASIST_L_SAMPLES // 2  # 50% overlap
    starts = list(range(0, len(waveform) - AASIST_L_SAMPLES + 1, stride))
    if len(starts) > max_windows:  # evenly subsample, always keeping both ends
        picks = np.linspace(0, len(starts) - 1, max_windows).round().astype(int)
        starts = [starts[i] for i in dict.fromkeys(picks.tolist())]
    return np.stack([waveform[s:s + AASIST_L_SAMPLES] for s in starts])


def _sigmoid(value: float) -> float:
    return float(1.0 / (1.0 + np.exp(-np.clip(value, -30.0, 30.0))))


def score_spoof(waveform_16k: np.ndarray) -> float:
    """Return calibrated-model input evidence in [0, 1], where higher is more spoof-like.

    AASIST-L ONNX exports a single ``spoof_logit`` (spoof logit minus bonafide
    logit). This conversion exactly preserves the two-class softmax spoof score.
    """
    settings = get_settings()
    if settings.model_backend == "aasist-l-onnx":
        session = _try_onnx(settings.aasist_l_onnx)
        if session is not None:
            windows = _aasist_windows(waveform_16k)
            output = session.run(None, {session.get_inputs()[0].name: windows})[0]
            logits = np.asarray(output, dtype=np.float64).reshape(-1)
            # Max over windows: a clone spliced into part of a call should raise
            # the whole call's score, so the most spoof-like window governs.
            return _sigmoid(float(np.max(logits)))
    if waveform_16k.size == 0:
        return 0.0
    # Development-only fallback: never describe this heuristic as model output.
    waveform = np.asarray(waveform_16k, dtype=np.float64)
    rms = float(np.sqrt(np.mean(waveform ** 2) + 1e-9))
    variance = float(np.var(waveform) + 1e-9)
    return float(max(0.0, min(0.95, 0.15 + min(0.6, rms * 2.0) * 0.4 + max(0.0, 0.5 - variance * 10) * 0.3)))
