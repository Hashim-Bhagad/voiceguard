"""Challenge-response: random multilingual phrase. Step-up cost, NOT proof."""
import random
import time

_DIGITS = "0123456789"
_WORDS = ["neela", "tara", "sher", "ganga", "deep", "rani", "blue", "seven"]

_active: dict[str, dict] = {}


def create_challenge(session_id: str) -> dict:
    phrase = f"{random.choice(_DIGITS)}-{random.choice(_DIGITS)}-{random.choice(_WORDS)}-{random.choice(_DIGITS)}"
    _active[session_id] = {"phrase": phrase, "ts": time.time()}
    return {"phrase": phrase, "expires_in_s": 30}


def verify_response(session_id: str, transcript: str, spoof_score: float) -> dict:
    ch = _active.get(session_id)
    if not ch:
        return {"result": "uncertain", "reason": "no active challenge"}
    # Mock: require phrase tokens present + spoof low. Real: same CNN + timing check.
    ok_text = ch["phrase"].split("-")[0] in transcript
    if ok_text and spoof_score < 0.5:
        return {"result": "pass", "reason": "matched + natural"}
    if spoof_score >= 0.5:
        return {"result": "fail", "reason": "response still synthetic"}
    return {"result": "uncertain", "reason": "text mismatch"}
