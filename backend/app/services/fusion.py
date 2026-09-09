"""Fusion: calibrated stub + smoothing + policy thresholds. Keeps components separate."""
from collections import deque
from app.schemas.contracts import POLICY_DEFAULTS

_smooth: dict[str, deque] = {}


def _ema(session_id: str, value: float, alpha: float = 0.4) -> float:
    q = _smooth.setdefault(session_id, deque(maxlen=8))
    q.append(value)
    # simple EMA over queue
    e = q[0]
    for v in list(q)[1:]:
        e = alpha * v + (1 - alpha) * e
    return float(e)


def fuse(
    session_id: str,
    spoof: float,
    linguistic: float,
    speaker_match: float | None,
    context_risk: float,
    prosody_flat: bool,
    policy_profile: str,
) -> tuple[float, str, str]:
    # Transparent weights (version with policy_ver). TODO: logistic + temperature scaling from dev set.
    w_spoof, w_ling, w_ctx = 0.55, 0.25, 0.20
    raw = w_spoof * spoof + w_ling * linguistic + w_ctx * context_risk
    if prosody_flat:
        raw += 0.05
    if speaker_match is not None and speaker_match < 0.35:
        raw += 0.10  # identity mismatch boosts, kept separate in telemetry
    raw = max(0.0, min(0.99, raw))
    final = _ema(session_id, raw)

    thr = POLICY_DEFAULTS.get(policy_profile, POLICY_DEFAULTS["standard"])
    if final >= thr.high_thr:
        return final, "high", "hold"
    if final >= thr.low_thr:
        # challenge only on high; review asks verify
        return final, "review", "verify"
    return final, "low", "continue"
