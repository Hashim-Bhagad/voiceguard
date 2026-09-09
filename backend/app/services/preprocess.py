"""Preprocess: validate PCM16 frames -> float32 mono 16k normalized. Preserve src meta."""
import numpy as np


def pcm16_to_float32(raw: bytes) -> np.ndarray:
    if not raw:
        return np.zeros(0, dtype=np.float32)
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return pcm


def normalize(chunk: np.ndarray, target_rms: float = 0.1) -> np.ndarray:
    rms = float(np.sqrt(np.mean(chunk.astype(np.float64) ** 2) + 1e-12))
    if rms < 1e-6:
        return chunk.astype(np.float32)
    gain = min(5.0, target_rms / rms)
    return (chunk * gain).astype(np.float32)
