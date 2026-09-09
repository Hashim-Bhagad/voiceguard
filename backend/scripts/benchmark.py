"""Benchmark streaming path on this machine. Reports p50/p95 + time-to-first-score."""
import time
import numpy as np
from app.services import model_registry, vad
from app.services.ring_buffer import RingBuffer
from app.services.preprocess import normalize


def main():
    sr = 16000
    rb = RingBuffer()
    rng = np.random.default_rng(0)
    lat = []
    t0 = time.time()
    first_score = None
    for i in range(40):  # 40 x 100ms frames = 4s
        chunk = (rng.standard_normal(1600) * 0.05).astype(np.float32)
        rb.append(normalize(chunk))
        w = rb.window(1.5)
        t = time.time()
        s = model_registry.score_spoof(w) if w.size else 0.0
        lat.append((time.time() - t) * 1000)
        if first_score is None and w.size and vad.is_speech(w[-3200:]):
            first_score = time.time() - t0
    lat = sorted(lat)
    print(f"backend={model_registry.backend_name()} ver={model_registry.model_version()}")
    print(f"p50={lat[len(lat)//2]:.1f}ms p95={lat[int(len(lat)*0.95)]:.1f}ms time_to_first_score={first_score:.2f}s (mock audio)")


if __name__ == "__main__":
    main()
