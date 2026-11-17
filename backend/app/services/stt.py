"""Speech-to-Text service using Groq Whisper Cloud API (ultra-low latency)."""
from __future__ import annotations

import io
import logging
import os
from typing import Optional

from app.core.config import get_settings

log = logging.getLogger("voiceguard.stt")

_groq_client = None


def get_groq_client():
    global _groq_client
    if _groq_client is not None:
        return _groq_client

    settings = get_settings()
    api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY")
    if not api_key:
        log.warning("GROQ_API_KEY not configured. Automatic transcription disabled.")
        return None

    try:
        from groq import Groq
        _groq_client = Groq(api_key=api_key)
        return _groq_client
    except Exception as e:
        log.error("Failed to initialize Groq client: %s", e)
        return None


def _field(obj, name):
    """Read a field from an SDK object or a plain dict (verbose_json responses)."""
    if isinstance(obj, dict):
        return obj.get(name)
    value = getattr(obj, name, None)
    if value is None:
        extra = getattr(obj, "model_extra", None) or {}
        value = extra.get(name)
    return value


def transcribe_audio_detailed(raw_audio_bytes: bytes, filename: str = "input.wav", lang_hint: Optional[str] = None) -> dict:
    """Transcribe and report the language.

    Returns ``{"text", "language", "language_source"}``. ``language`` is what
    Whisper detected (verbose_json), or the hint when one was forced; source is
    ``"whisper"``, ``"hint"`` or ``"none"`` so the UI never presents an echoed
    hint as a detection.
    """
    # "auto" and "auto-hinglish" mean "detect": Whisper rejects them as language codes.
    hinted = lang_hint if lang_hint and not lang_hint.startswith("auto") and lang_hint != "unknown" else None
    empty = {"text": "", "language": hinted or "auto", "language_source": "hint" if hinted else "none"}
    client = get_groq_client()
    if not client or not raw_audio_bytes:
        return empty

    try:
        # Determine valid filename extension
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".wav", ".mp3", ".webm", ".m4a", ".ogg", ".flac"]:
            ext = ".wav"
        file_obj = io.BytesIO(raw_audio_bytes)
        file_obj.name = f"audio{ext}"

        kwargs = {
            "file": file_obj,
            "model": "whisper-large-v3-turbo",
            "response_format": "verbose_json",
        }
        if hinted:
            kwargs["language"] = hinted

        transcription = client.audio.transcriptions.create(**kwargs)
        text = str(_field(transcription, "text") or "").strip()
        detected = _field(transcription, "language")
        log.info("Transcribed %d bytes audio (%s): '%s'", len(raw_audio_bytes), detected, text[:80])
        if hinted:
            return {"text": text, "language": hinted, "language_source": "hint"}
        if detected:
            return {"text": text, "language": str(detected).strip().lower(), "language_source": "whisper"}
        return {"text": text, "language": "auto", "language_source": "none"}
    except Exception as e:
        log.error("Groq STT transcription error: %s", e)
        return empty


def transcribe_audio(raw_audio_bytes: bytes, filename: str = "input.wav", lang_hint: Optional[str] = None) -> str:
    """Transcribe audio bytes using Groq Whisper API (text only)."""
    return transcribe_audio_detailed(raw_audio_bytes, filename, lang_hint)["text"]
