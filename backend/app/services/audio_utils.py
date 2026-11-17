"""Audio decoding, resampling, and normalization utilities for VoiceGuard."""
from __future__ import annotations

import io
import logging
import wave
import numpy as np

log = logging.getLogger("voiceguard.audio")


def _decode_with_ffmpeg(raw_bytes: bytes) -> np.ndarray | None:
    """Decode any container/codec ffmpeg understands to 16 kHz mono float32, or None."""
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        return None
    try:
        proc = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-i", "pipe:0", "-t", "600",
             "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "pipe:1"],
            input=raw_bytes, capture_output=True, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("ffmpeg decode failed: %s", exc)
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def decode_audio_to_16k_mono(raw_bytes: bytes) -> np.ndarray:
    """Decodes arbitrary incoming audio (WAV, PCM16, WebM/OGG via soundfile)
    into a canonical 1D float32 numpy array normalized to [-1.0, 1.0] at 16 kHz.
    """
    if not raw_bytes or len(raw_bytes) < 4:
        return np.zeros(0, dtype=np.float32)

    # 1. Try standard WAV decoding
    try:
        with wave.open(io.BytesIO(raw_bytes), "rb") as w:
            channels = w.getnchannels()
            rate = w.getframerate()
            sampwidth = w.getsampwidth()
            n_frames = w.getnframes()
            frames = w.readframes(n_frames)

            if sampwidth == 2:
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            elif sampwidth == 4:
                audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
            elif sampwidth == 1:
                audio = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
            else:
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

            if channels > 1:
                audio = audio.reshape(-1, channels).mean(axis=1)

            # Simple resample to 16kHz if needed
            if rate != 16000 and len(audio) > 0 and rate > 0:
                new_len = int(round(len(audio) * 16000 / rate))
                audio = np.interp(
                    np.linspace(0, len(audio), new_len, endpoint=False),
                    np.arange(len(audio)),
                    audio
                ).astype(np.float32)

            return audio
    except Exception:
        pass

    # 2. Try soundfile (supports WebM, OGG, FLAC, WAV)
    try:
        import soundfile as sf
        audio, rate = sf.read(io.BytesIO(raw_bytes), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if rate != 16000 and len(audio) > 0 and rate > 0:
            new_len = int(round(len(audio) * 16000 / rate))
            audio = np.interp(
                np.linspace(0, len(audio), new_len, endpoint=False),
                np.arange(len(audio)),
                audio
            ).astype(np.float32)
        return audio
    except Exception:
        pass

    # 3. ffmpeg: browser recordings (WebM/Opus from Chrome, MP4/AAC from Safari) and
    #    uploads like MP3/M4A, none of which libsndfile can read. Without this they fell
    #    through to the raw-PCM guess below and the model scored noise.
    audio = _decode_with_ffmpeg(raw_bytes)
    if audio is not None:
        return audio

    # 4. Fallback: treat as raw PCM16
    try:
        usable_bytes = len(raw_bytes) - (len(raw_bytes) % 2)
        if usable_bytes > 0:
            return np.frombuffer(raw_bytes[:usable_bytes], dtype=np.int16).astype(np.float32) / 32768.0
    except Exception as e:
        log.warning("Failed raw PCM fallback: %s", e)

    return np.zeros(0, dtype=np.float32)
