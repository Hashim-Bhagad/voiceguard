"""Alert bus: in-app + log now; SMS/push/email gateway stub."""
import logging

log = logging.getLogger("voiceguard.alerts")
_events: list[dict] = []


def emit(session_id: str, state: str, final_risk: float, action: str, channels=("inapp",)):
    evt = {"session_id": session_id, "state": state, "final_risk": final_risk, "action": action, "channels": list(channels)}
    _events.append(evt)
    if state == "high":
        log.warning("HIGH RISK %.2f session=%s action=%s — HOLD txn, OTP/callback required", final_risk, session_id, action)
    return evt


def recent(n: int = 50) -> list[dict]:
    return _events[-n:]
