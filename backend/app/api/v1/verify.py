import time
import uuid
from fastapi import APIRouter, UploadFile, File, Form
from app.schemas.contracts import VerifyResponse
from app.services import model_registry, prosody, linguistic, fusion, stt, audio_utils, firestore_service, explainability
from app.core.config import get_settings

router = APIRouter()


@router.post("/verify/file", response_model=VerifyResponse)
async def verify_file(
    file: UploadFile = File(...),
    policy_profile: str = Form("standard"),
    lang_hint: str = Form("auto"),
    transcript: str = Form(""),
    session_id: str = Form(""),
    caller_id: str = Form("Web Client"),
):
    raw_bytes = await file.read()
    session_id = session_id.strip() or f"call_{uuid.uuid4().hex[:8]}"

    # 1. Decode audio to 16kHz mono float32
    audio = audio_utils.decode_audio_to_16k_mono(raw_bytes)
    has_audio = audio.size > 0

    # 2. Transcribe via Groq Whisper if transcript was not manually supplied
    final_transcript = transcript.strip()
    hinted = lang_hint if lang_hint and not lang_hint.startswith("auto") else None
    language = {"language": hinted or "auto", "language_source": "hint" if hinted else "none"}
    if not final_transcript and raw_bytes:
        heard = stt.transcribe_audio_detailed(raw_bytes, filename=file.filename or "input.wav", lang_hint=lang_hint)
        final_transcript = heard["text"]
        language = {"language": heard["language"], "language_source": heard["language_source"]}

    # 3. Acoustic Spoof Detection via AASIST-L ONNX
    # Per-window scores come from the same inference as the clip score.
    spoof_score, segments = model_registry.score_spoof_detailed(audio) if has_audio else (0.0, [])
    spoof_score = float(spoof_score)

    # 4. Multilingual Linguistic Urgency Analysis
    ling_score, matched_flags = linguistic.score_text(final_transcript)

    # 5. Prosody & Quality
    prosody_is_flat = prosody.prosody_flag(audio) == "flat" if has_audio else False
    quality = "ok" if has_audio and len(audio) >= 8000 else "insufficient"

    # 6. Context Risk & Fusion
    ctx_risk = 0.6 if policy_profile == "high-value-txn" else 0.2
    final_risk, state, action = fusion.fuse(
        session_id=session_id,
        spoof=spoof_score,
        linguistic=ling_score,
        speaker_match=None,
        context_risk=ctx_risk,
        prosody_flat=prosody_is_flat,
        policy_profile=policy_profile,
    )

    if not has_audio:
        state = "insufficient"
        action = "continue"

    challenge_triggered = (action == "challenge") or (final_risk >= 0.50)
    s = get_settings()

    # 7. Explainability & Forensic Report
    forensic_report = explainability.generate_forensic_report(
        audio_16k=audio,
        linguistic_hits=matched_flags,
        spoof_score=spoof_score,
        prosody_flag="flat" if prosody_is_flat else "normal",
    )
    fusion_breakdown = fusion.get_fusion_breakdown(
        spoof=spoof_score,
        linguistic=ling_score,
        context_risk=ctx_risk,
        prosody_flat=prosody_is_flat,
    )

    # 8. Persist Telemetry to Firestore (Never raw audio)
    session_record = {
        "session_id": session_id,
        "caller": caller_id,
        "final_risk": final_risk,
        "state": state,
        "action": action,
        "spoof_score": spoof_score,
        "linguistic_score": ling_score,
        "transcript": final_transcript,
        "flags": matched_flags,
        "timestamp": int(time.time() * 1000),
        "policy_profile": policy_profile,
        "diagnostic_summary": forensic_report["diagnostic_reasons"][:2],
    }
    firestore_service.save_session(session_record)

    if state == "high" or action in ("hold", "challenge"):
        firestore_service.save_alert({
            "session_id": session_id,
            "caller": caller_id,
            "final_risk": final_risk,
            "state": state,
            "action": action,
            "reason": f"High risk detected ({final_risk*100:.1f}%). Triggering step-up verification.",
            "flags": matched_flags,
            "timestamp": int(time.time() * 1000),
        })

    return VerifyResponse(
        seq=0,
        server_ts=int(time.time() * 1000),
        vad=has_audio,
        quality=quality,
        spoof_score=spoof_score,
        acoustic_risk_score=spoof_score,
        linguistic_score=ling_score,
        linguistic_risk_score=ling_score,
        transcript_delta=final_transcript,
        transcript=final_transcript,
        context_risk=ctx_risk,
        final_risk=final_risk,
        final_risk_score=final_risk,
        state=state,
        action=action,
        model_ver=model_registry.model_version(),
        policy_ver=s.policy_ver,
        session_id=session_id,
        segments=segments,
        flags=matched_flags,
        challenge_triggered=challenge_triggered,
        lang_detected=language["language"],
        lang_source=language["language_source"],
        explainability=forensic_report,
        fusion_breakdown=fusion_breakdown,
        privacy_attestation={
            "zero_raw_audio_stored": True,
            "ephemeral_ram_buffer": True,
            "compliance": "DPDP Act 2023 Compliant",
            "retention_policy": "Derived acoustic features & transcript only; audio waveform discarded post-inference",
        },
    )

