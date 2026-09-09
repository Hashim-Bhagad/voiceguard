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


def transcribe_audio(raw_audio_bytes: bytes, filename: str = "input.wav", lang_hint: Optional[str] = None) -> str:
    """Transcribe audio bytes using Groq Whisper API."""
    client = get_groq_client()
    if not client or not raw_audio_bytes:
        return ""

    try:
        # Determine valid filename extension
        ext = os.path.splitext(filename)[1].lower()
        if ext not in [".wav", ".mp3", ".webm", ".m4a", ".ogg", ".flac"]:
            ext = ".wav"
        file_name = f"audio{ext}"

        file_obj = io.BytesIO(raw_audio_bytes)
        file_obj.name = file_name

        kwargs = {
            "file": file_obj,
            "model": "whisper-large-v3-turbo",
            "response_format": "text",
        }
        if lang_hint and lang_hint not in ("auto", "unknown", ""):
            kwargs["language"] = lang_hint

        transcription = client.audio.transcriptions.create(**kwargs)
        result = str(transcription).strip()
        log.info("Transcribed %d bytes audio: '%s'", len(raw_audio_bytes), result[:80])
        return result
    except Exception as e:
        log.error("Groq STT transcription error: %s", e)
        return ""
