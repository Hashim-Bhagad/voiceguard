"""Challenge-response verification service.
Generates dynamic multilingual phrases, enforces strict 30-second expiry,
and verifies both spoken transcript tokens and acoustic liveness.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict

from app.services import audio_utils, model_registry, stt, firestore_service

log = logging.getLogger("voiceguard.challenge")

_DIGITS = ["2", "3", "4", "5", "6", "7", "8", "9"]
_WORDS = ["neela", "tara", "sher", "ganga", "deep", "rani", "blue", "seven", "suraj", "chandra"]

# Active in-flight challenges: session_id -> {phrase, tokens, ts}
_active: dict[str, dict] = {}
EXPIRY_SECONDS = 30


def create_challenge(session_id: str) -> dict:
    """Generate a truly random multilingual phrase bound to session_id."""
    tokens = [random.choice(_DIGITS), random.choice(_DIGITS), random.choice(_WORDS), random.choice(_DIGITS)]
    phrase = "-".join(tokens)
    now = time.time()
    _active[session_id] = {
        "phrase": phrase,
        "tokens": tokens,
        "ts": now,
    }
    log.info("Issued challenge '%s' for session %s (expires in %ds)", phrase, session_id, EXPIRY_SECONDS)
    return {
        "session_id": session_id,
        "phrase": phrase,
        "tokens": tokens,
        "display_code": " ".join(tokens),
        "expires_in_s": EXPIRY_SECONDS,
    }


def verify_challenge_audio(session_id: str, audio_bytes: bytes, filename: str = "response.wav") -> dict:
    """End-to-end verification of challenge response audio:
    1. Checks challenge existence and TTL expiry.
    2. Runs Groq Whisper STT on response audio.
    3. Verifies spoken tokens match the generated challenge.
    4. Runs AASIST-L acoustic CNN to ensure the response is not cloned/replayed.
    5. Clears the challenge to prevent replay attacks.
    """
    ch = _active.pop(session_id, None)
    if not ch:
        return {"result": "uncertain", "reason": "No active challenge found for this session"}

    elapsed = time.time() - ch["ts"]
    if elapsed > EXPIRY_SECONDS:
        return {"result": "fail", "reason": f"Challenge expired ({elapsed:.1f}s > {EXPIRY_SECONDS}s)"}

    # Transcribe response audio
    transcript = stt.transcribe_audio(audio_bytes, filename=filename)
    transcript_lower = transcript.lower()

    # Check tokens match
    tokens = ch["tokens"]
    matched_tokens = [t for t in tokens if t.lower() in transcript_lower]
    match_ratio = len(matched_tokens) / len(tokens) if tokens else 0.0

    # Acoustic spoof score
    audio = audio_utils.decode_audio_to_16k_mono(audio_bytes)
    spoof_score = float(model_registry.score_spoof(audio)) if audio.size > 0 else 0.0

    result = "uncertain"
    reason = ""

    if match_ratio >= 0.60:
        if spoof_score < 0.45:
            result = "pass"
            reason = f"Spoken phrase matched ({len(matched_tokens)}/{len(tokens)} tokens) with natural acoustic liveness"
        else:
            result = "fail"
            reason = f"Phrase matched but acoustic detector flagged synthetic voice (spoof: {spoof_score:.2f})"
    else:
        result = "fail"
        reason = f"Challenge phrase mismatch. Spoken: '{transcript}', expected: '{ch['phrase']}'"

    log.info("Challenge verification for %s: %s (%s)", session_id, result, reason)
    return {
        "session_id": session_id,
        "result": result,
        "reason": reason,
        "phrase": ch["phrase"],
        "transcript": transcript,
        "spoof_score": spoof_score,
        "matched_tokens": matched_tokens,
    }


def verify_response(session_id: str, transcript: str, spoof_score: float) -> dict:
    """Legacy/API fallback verification when transcript is precomputed."""
    ch = _active.pop(session_id, None)
    if not ch:
        return {"result": "uncertain", "reason": "no active challenge"}

    elapsed = time.time() - ch["ts"]
    if elapsed > EXPIRY_SECONDS:
        return {"result": "fail", "reason": "challenge expired"}

    t_lower = transcript.lower()
    tokens = ch.get("tokens", ch["phrase"].split("-"))
    matched = [tok for tok in tokens if tok.lower() in t_lower]
    ok_text = len(matched) >= len(tokens) // 2 + 1

    if ok_text and spoof_score < 0.45:
        return {"result": "pass", "reason": "matched + natural"}
    if spoof_score >= 0.45:
        return {"result": "fail", "reason": "response still synthetic"}
    return {"result": "uncertain", "reason": f"text mismatch (expected '{ch['phrase']}', heard '{transcript}')"}
