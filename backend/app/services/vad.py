"""VAD + quality gates. Mock energy VAD now; swap Silero in full deps."""
import numpy as np


def is_speech(chunk: np.ndarray, thresh: float = 0.01) -> bool:
    if chunk.size == 0:
        return False
    rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2) + 1e-12))
    return rms > thresh


def quality_flag(chunk: np.ndarray, seconds_buffered: float) -> str:
    if seconds_buffered < 1.0 or chunk.size < 16000:
        return "insufficient"
    # TODO(full): estimate clipping, packet-loss gaps, bandwidth (8k vs 16k).
    return "ok"
