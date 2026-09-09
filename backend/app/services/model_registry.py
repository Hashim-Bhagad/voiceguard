"""Lazy CPU ONNX AASIST-L registry with a mock fallback for UI development."""
import os

import numpy as np

from app.core.config import get_settings

AASIST_L_SAMPLES = 64600
_loaded: dict[str, object] = {}


def backend_name() -> str:
    return get_settings().model_backend


def model_version() -> str:
    return "aasist-l-indic-v0.1" if get_settings().model_backend == "aasist-l-onnx" else "mock-v0.1"


def _try_onnx(path: str):
    if path in _loaded:
        return _loaded[path]
    if not os.path.exists(path):
        return None
    try:
        import onnxruntime as ort

        session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        _loaded[path] = session
        return session
    except Exception:
        return None


def _aasist_window(waveform_16k: np.ndarray) -> np.ndarray:
    """Match fine-tuning: mono float32 @16 kHz, fixed 64,600 sample window."""
    waveform = np.asarray(waveform_16k, dtype=np.float32).reshape(-1)
    if len(waveform) >= AASIST_L_SAMPLES:
        return waveform[-AASIST_L_SAMPLES:]
    return np.pad(waveform, (0, AASIST_L_SAMPLES - len(waveform)))


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
            output = session.run(None, {session.get_inputs()[0].name: _aasist_window(waveform_16k)[None, :]})[0]
            return _sigmoid(float(np.asarray(output).reshape(-1)[0]))
    if waveform_16k.size == 0:
        return 0.0
    # Development-only fallback: never describe this heuristic as model output.
    waveform = np.asarray(waveform_16k, dtype=np.float64)
    rms = float(np.sqrt(np.mean(waveform ** 2) + 1e-9))
    variance = float(np.var(waveform) + 1e-9)
    return float(max(0.0, min(0.95, 0.15 + min(0.6, rms * 2.0) * 0.4 + max(0.0, 0.5 - variance * 10) * 0.3)))
