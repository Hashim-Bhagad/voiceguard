import time
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form
from app.schemas.contracts import VerifyResponse, POLICY_DEFAULTS
from app.services import model_registry, prosody, linguistic, fusion
from app.core.config import get_settings

router = APIRouter()


@router.post("/verify/file", response_model=VerifyResponse)
async def verify_file(
    file: UploadFile = File(...),
    policy_profile: str = Form("standard"),
    lang_hint: str = Form("auto"),
    transcript: str = Form(""),
):
    raw = await file.read()
    # Assume 16k mono PCM16 or wav; best-effort decode: try PCM16 else zeros.
    try:
        import io, wave
        with wave.open(io.BytesIO(raw), "rb") as w:
            n = w.getnframes()
            pcm = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        # raw pcm16 fallback
        pcm = np.frombuffer(raw[:32000 * 2], dtype=np.int16).astype(np.float32) / 32768.0
    window = pcm[: 16000 * 2] if pcm.size else np.zeros(0, dtype=np.float32)

    spoof = model_registry.score_spoof(window)
    ling, _ = linguistic.score_text(transcript)
    ctx = 0.6 if policy_profile == "high-value-txn" else 0.2
    final, state, action = fusion.fuse("batch", spoof, ling, None, ctx, prosody.prosody_flag(window) == "flat", policy_profile)
    s = get_settings()
    return VerifyResponse(
        seq=0, server_ts=int(time.time() * 1000), vad=True,
        quality="ok" if window.size else "insufficient",
        spoof_score=spoof, linguistic_score=ling, transcript_delta=transcript,
        context_risk=ctx, final_risk=final, state=state if window.size else "insufficient",
        action=action, model_ver=model_registry.model_version(), policy_ver=s.policy_ver,
        session_id="batch", segments=[],
    )
