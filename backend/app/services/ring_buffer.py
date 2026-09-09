"""Bounded ring buffer: RAM only, never disk. 5-10s max."""
from collections import deque
import numpy as np


class RingBuffer:
    def __init__(self, max_seconds: float = 8.0, sample_rate: int = 16000):
        self.max_samples = int(max_seconds * sample_rate)
        self.buf: deque = deque()
        self.n = 0

    def append(self, chunk: np.ndarray):
        self.buf.append(np.asarray(chunk, dtype=np.float32))
        self.n += len(chunk)
        # evict oldest
        while self.n > self.max_samples and self.buf:
            old = self.buf.popleft()
            self.n -= len(old)

    def window(self, seconds: float = 1.5) -> np.ndarray:
        need = int(seconds * 16000)
        if self.n < need:
            return np.zeros(0, dtype=np.float32)
        out = np.concatenate(list(self.buf))[-need:]
        return out.astype(np.float32)

    def seconds_buffered(self) -> float:
        return self.n / 16000.0
