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


_digests: dict[tuple[str, int, float], str] = {}


def _file_sha256(path: Path) -> str:
    """SHA-256 of the model file, cached per (path, size, mtime).

    /health is hit on every page load (it also wakes the server), and hashing a
    several-hundred-MB model each time costs seconds on a small shared CPU.
    """
    stat = path.stat()
    key = (str(path.resolve()), stat.st_size, stat.st_mtime)
    if key not in _digests:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        _digests[key] = digest.hexdigest()
    return _digests[key]


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
        status["model_sha256"] = _file_sha256(path)
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


def _window_starts(n_samples: int, max_windows: int = 8) -> list[int]:
    """Sample offsets of the windows that cover a clip of ``n_samples``."""
    if n_samples <= AASIST_L_SAMPLES:
        return [0]
    stride = AASIST_L_SAMPLES // 2  # 50% overlap
    starts = list(range(0, n_samples - AASIST_L_SAMPLES + 1, stride))
    if len(starts) > max_windows:  # evenly subsample, always keeping both ends
        picks = np.linspace(0, len(starts) - 1, max_windows).round().astype(int)
        starts = [starts[i] for i in dict.fromkeys(picks.tolist())]
    return starts


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
    starts = _window_starts(len(waveform), max_windows)
    return np.stack([waveform[s:s + AASIST_L_SAMPLES] for s in starts])


def _sigmoid(value: float) -> float:
    return float(1.0 / (1.0 + np.exp(-np.clip(value, -30.0, 30.0))))


def _aggregate(logits: np.ndarray) -> float:
    """Combine per-window logits into one clip-level logit.

    Measured on the 454-clip held-out test split via scripts/tune_decision_layer.py
    (175 genuine / 279 spoof). FPR@95%TPR is the share of genuine callers flagged
    while still catching 95% of clones -- lower is better:

        aggregation        EER      FPR@95%TPR
        max                0.2354   0.531
        mean               0.2336   0.480   <- default
        median             0.2336   0.486
        trimmed_mean_20    0.2354   0.480

    'mean' is the default because it cuts the false-positive rate by ~5 points
    against 'max' at equal spoof recall, for free.

    The tradeoff worth knowing: 'max' is more sensitive to a clone spliced into
    only part of a longer call, since one synthetic window drives the whole
    score. If partial-splice attacks matter more to you than false positives,
    set VOICEGUARD_SCORE_AGG=max. On this test set only 52 of 454 clips were
    long enough to produce more than one window, so the practical difference
    here is small; it grows with call length.
    """
    if logits.size == 1:
        return float(logits[0])
    mode = os.getenv("VOICEGUARD_SCORE_AGG", "mean").lower()
    if mode == "max":
        return float(np.max(logits))
    if mode == "median":
        return float(np.median(logits))
    return float(np.mean(logits))


def _calibration_offset() -> float:
    """Logit of SPOOF_OPERATING_THRESHOLD; subtracting it maps that threshold to 0.5.

    A pure shift in logit space: the ranking of clips (and so EER/AUC) is
    unchanged, only where 0.5 falls moves.
    """
    threshold = float(get_settings().spoof_operating_threshold)
    if not 0.0 < threshold < 1.0:
        raise ValueError(f"SPOOF_OPERATING_THRESHOLD must be in (0, 1), got {threshold}")
    return float(np.log(threshold / (1.0 - threshold)))


def score_spoof_detailed(waveform_16k: np.ndarray, sample_rate: int = 16000) -> tuple[float, list[dict]]:
    """Clip score plus the per-window scores it was aggregated from.

    The windows are the ones ``score_spoof`` already runs, so the timeline costs no
    extra inference. Each segment is ``{"start_s", "end_s", "spoof_score"}`` with the
    same calibration as the clip score. When the neural model is not running the
    heuristic fallback has no windows, and segments is empty rather than invented.
    """
    settings = get_settings()
    if settings.model_backend == "aasist-l-onnx":
        session = _try_onnx(settings.aasist_l_onnx)
        if session is not None:
            waveform = np.asarray(waveform_16k, dtype=np.float32).reshape(-1)
            windows = _aasist_windows(waveform)
            output = session.run(None, {session.get_inputs()[0].name: windows})[0]
            logits = np.asarray(output, dtype=np.float64).reshape(-1)
            offset = _calibration_offset()
            starts = _window_starts(len(waveform))
            duration = len(waveform) / sample_rate
            segments = [
                {
                    "start_s": round(start / sample_rate, 2),
                    "end_s": round(min(duration, (start + AASIST_L_SAMPLES) / sample_rate), 2),
                    "spoof_score": round(_sigmoid(float(logit) - offset), 4),
                }
                for start, logit in zip(starts, logits)
            ]
            return _sigmoid(_aggregate(logits) - offset), segments
    return _heuristic_score(waveform_16k), []


def score_spoof(waveform_16k: np.ndarray) -> float:
    """Return calibrated-model input evidence in [0, 1], where higher is more spoof-like.

    AASIST-L ONNX exports a single ``spoof_logit`` (spoof logit minus bonafide
    logit). With SPOOF_OPERATING_THRESHOLD at its default of 0.5 this conversion
    exactly preserves the two-class softmax spoof score; otherwise the score is
    shifted so that threshold reads as 0.5 (see _calibration_offset).
    """
    return score_spoof_detailed(waveform_16k)[0]


def _heuristic_score(waveform_16k: np.ndarray) -> float:
    if waveform_16k.size == 0:
        return 0.0
    # Development-only fallback: never describe this heuristic as model output.
    waveform = np.asarray(waveform_16k, dtype=np.float64)
    rms = float(np.sqrt(np.mean(waveform ** 2) + 1e-9))
    variance = float(np.var(waveform) + 1e-9)
    return float(max(0.0, min(0.95, 0.15 + min(0.6, rms * 2.0) * 0.4 + max(0.0, 0.5 - variance * 10) * 0.3)))
