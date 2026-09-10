"""Challenge-response verification service.
Generates dynamic 4-digit challenges ("Please repeat 4-7-2-9"), enforces strict 30-second expiry,
evaluates response latency (deepfake pipelines lag >2.5s), and verifies spoken transcript & acoustic liveness.
"""
from __future__ import annotations

import logging
import random
import re
import time
from typing import Any, Dict

from app.services import audio_utils, model_registry, stt, firestore_service, explainability

log = logging.getLogger("voiceguard.challenge")

_DIGITS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"]

# Multilingual digit word mapping for STT transcripts
DIGIT_WORD_MAP: dict[str, str] = {
    # English
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    # Hindi / Hinglish
    "shunya": "0", "ek": "1", "do": "2", "teen": "3", "char": "4",
    "chaar": "4", "paanch": "5", "panch": "5", "chhe": "6", "che": "6",
    "saat": "7", "sat": "7", "aath": "8", "ath": "8", "nau": "9", "no": "9",
    "एक": "1", "दो": "2", "तीन": "3", "चार": "4", "पांच": "5", 
    "छह": "6", "सात": "7", "आठ": "8", "नौ": "9", "शून्य": "0"
}

# Active in-flight challenges: session_id -> {code, tokens, prompt, ts}
_active: dict[str, dict] = {}
EXPIRY_SECONDS = 30


def create_challenge(session_id: str) -> dict:
    """Generate a dynamic 4-digit challenge bound to session_id."""
    tokens = [random.choice(_DIGITS) for _ in range(4)]
    display_code = " ".join(tokens)
    phrase = "-".join(tokens)
    prompt = f"Please repeat the numbers: {', '.join(tokens)}"
    now = time.time()
    
    _active[session_id] = {
        "phrase": phrase,
        "tokens": tokens,
        "display_code": display_code,
        "prompt": prompt,
        "ts": now,
    }
    log.info("Issued challenge '%s' for session %s (expires in %ds)", display_code, session_id, EXPIRY_SECONDS)
    return {
        "session_id": session_id,
        "display_code": display_code,
        "phrase": phrase,
        "tokens": tokens,
        "prompt": prompt,
        "expires_in_s": EXPIRY_SECONDS,
        "issued_at": int(now * 1000),
    }


def _extract_digits_from_transcript(transcript: str) -> list[str]:
    """Normalize and extract spoken digits from transcript (numbers and words)."""
    t_clean = re.sub(r"[^\w\s\u0900-\u097F]", " ", transcript.lower())
    words = t_clean.split()
    extracted: list[str] = []

    for w in words:
        if w in _DIGITS or w == "0":
            extracted.append(w)
        elif w in DIGIT_WORD_MAP:
            extracted.append(DIGIT_WORD_MAP[w])
        else:
            # Check characters if glued together e.g. "4729"
            for ch in w:
                if ch in _DIGITS or ch == "0":
                    extracted.append(ch)

    return extracted


def verify_challenge_audio(session_id: str, audio_bytes: bytes, filename: str = "response.wav") -> dict:
    """End-to-end verification of challenge response audio:
    1. Checks challenge existence and TTL expiry.
    2. Measures response latency (real-time deepfake pipelines struggle with arbitrary unseen text).
    3. Runs Groq Whisper STT on response audio.
    4. Extracts and matches spoken digits against target challenge.
    5. Runs acoustic spoof detection & pitch jitter forensics.
    """
    now = time.time()
    ch = _active.pop(session_id, None)
    if not ch:
        return {
            "session_id": session_id,
            "result": "uncertain",
            "reason": "No active challenge found for this session. A challenge must be requested first.",
            "latency_ms": 0,
        }

    elapsed = now - ch["ts"]
    latency_ms = int(elapsed * 1000)

    if elapsed > EXPIRY_SECONDS:
        return {
            "session_id": session_id,
            "result": "fail",
            "reason": f"Challenge expired ({elapsed:.1f}s > {EXPIRY_SECONDS}s window)",
            "latency_ms": latency_ms,
        }

    # Transcribe response audio
    transcript = stt.transcribe_audio(audio_bytes, filename=filename)
    spoken_digits = _extract_digits_from_transcript(transcript)
    expected_tokens = ch["tokens"]

    # Match tokens
    matched_count = sum(1 for tok in expected_tokens if tok in spoken_digits)
    match_ratio = matched_count / len(expected_tokens) if expected_tokens else 0.0

    # Acoustic spoof score & jitter forensics
    audio = audio_utils.decode_audio_to_16k_mono(audio_bytes)
    spoof_score = float(model_registry.score_spoof(audio)) if audio.size > 0 else 0.0
    jitter = explainability.extract_pitch_jitter(audio) if audio.size > 0 else 1.0

    # Pipeline latency indicator:
    # A human typically responds within 0.4s - 2.5s.
    # Few-shot voice cloning pipelines (STT -> text buffer -> neural TTS -> neural vocoder)
    # often take >2.8s for unseen text.
    latency_verdict = "natural_human_reflex" if latency_ms <= 3000 else "delayed_pipeline_latency"

    result = "fail"
    reasons: list[str] = []

    if match_ratio >= 0.75:
        if spoof_score < 0.45 and jitter >= 0.35:
            result = "pass"
            reasons.append(f"Spoken digits matched ({matched_count}/{len(expected_tokens)}) with verified natural vocal liveness.")
        elif spoof_score >= 0.45:
            result = "fail"
            reasons.append(f"Challenge digits repeated, but acoustic model detected synthetic voice synthesis (spoof: {int(spoof_score*100)}%).")
        elif jitter < 0.35:
            result = "fail"
            reasons.append(f"Challenge digits repeated, but unnatural pitch micro-jitter detected ({jitter:.2f}%): indicates pre-rendered or cloned speech.")
    else:
        result = "fail"
        reasons.append(f"Spoken digits mismatch. Expected: '{ch['display_code']}', heard: '{transcript}'.")

    primary_reason = " ".join(reasons)
    log.info("Challenge verification for %s: %s (%s)", session_id, result, primary_reason)

    return {
        "session_id": session_id,
        "result": result,
        "reason": primary_reason,
        "display_code": ch["display_code"],
        "transcript": transcript,
        "spoken_digits": spoken_digits,
        "expected_digits": expected_tokens,
        "matched_count": matched_count,
        "match_ratio": round(match_ratio, 2),
        "latency_ms": latency_ms,
        "latency_verdict": latency_verdict,
        "spoof_score": round(spoof_score, 3),
        "jitter_pct": round(jitter, 3),
    }


def verify_response(session_id: str, transcript: str, spoof_score: float) -> dict:
    """Legacy/API fallback verification when transcript is precomputed."""
    ch = _active.pop(session_id, None)
    if not ch:
        return {"result": "uncertain", "reason": "no active challenge"}

    elapsed = time.time() - ch["ts"]
    if elapsed > EXPIRY_SECONDS:
        return {"result": "fail", "reason": "challenge expired"}

    spoken_digits = _extract_digits_from_transcript(transcript)
    expected_tokens = ch.get("tokens", [])
    matched_count = sum(1 for tok in expected_tokens if tok in spoken_digits)
    ok_text = matched_count >= len(expected_tokens) * 0.75

    if ok_text and spoof_score < 0.45:
        return {"result": "pass", "reason": f"Matched digits ({matched_count}/{len(expected_tokens)}) + natural liveness"}
    if spoof_score >= 0.45:
        return {"result": "fail", "reason": "response flagged as synthetic audio"}
    return {"result": "fail", "reason": f"Digit mismatch (expected '{ch['display_code']}', heard '{transcript}')"}

