"""Prosody stubs: F0/pause/HNR later. Never standalone reject."""
import numpy as np


def prosody_flag(window: np.ndarray) -> str:
    """Return flat|normal|unknown. Mock: low variance -> flat."""
    if window.size < 8000:
        return "unknown"
    var = float(np.var(window.astype(np.float64)))
    # Placeholder heuristic; replace with F0 trajectory + pause stats in full build.
    return "flat" if var < 0.005 else "normal"
