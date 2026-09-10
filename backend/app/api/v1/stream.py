"""WebSocket streaming: init JSON -> binary PCM16 frames -> telemetry JSON @2-4Hz."""
import json
import time
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.schemas.contracts import InitMessage
from app.services import ring_buffer, vad, preprocess, model_registry, prosody, linguistic, speaker, fusion, alerts, explainability
from app.core.config import get_settings

router = APIRouter()


@router.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    settings = get_settings()
    try:
        raw_init = await ws.receive_text()
        init = InitMessage(**json.loads(raw_init))
    except Exception:
        await ws.close(code=1008)
        return

    rb = ring_buffer.RingBuffer(max_seconds=8.0, sample_rate=init.sample_rate)
    seq = 0
    transcript_acc = ""
    # Demo helper: client may send {"type":"transcript","text":"..."} to feed linguistic path
    # until Whisper is wired. Real STT plugs here.

    try:
        while True:
            msg = await ws.receive()
            if "bytes" in msg and msg["bytes"]:
                chunk = preprocess.pcm16_to_float32(msg["bytes"])
                chunk = preprocess.normalize(chunk)
                rb.append(chunk)
                seq += 1
            elif "text" in msg and msg["text"]:
                try:
                    ctl = json.loads(msg["text"])
                    if ctl.get("type") == "transcript":
                        transcript_acc = ctl.get("text", "")
                        continue
                    if ctl.get("type") == "close":
                        break
                except Exception:
                    continue
            else:
                continue

            window = rb.window(seconds=1.5)
            speech = vad.is_speech(window[-3200:] if window.size else window)
            quality = vad.quality_flag(window, rb.seconds_buffered())
            if quality == "insufficient" or not speech:
                tel = {
                    "seq": seq, "server_ts": int(time.time() * 1000), "vad": bool(speech),
                    "quality": "insufficient", "spoof_score": 0.0,
                    "speaker_match_score": None, "prosody_flag": "unknown",
                    "linguistic_score": 0.0, "transcript_delta": transcript_acc,
                    "context_risk": 0.0, "final_risk": 0.0, "state": "insufficient",
                    "action": "continue", "model_ver": model_registry.model_version(),
                    "policy_ver": settings.policy_ver,
                }
                await ws.send_text(json.dumps(tel))
                continue

            spoof = model_registry.score_spoof(window)
            pflag = prosody.prosody_flag(window)
            ling, matched_hits = linguistic.score_text(transcript_acc)
            spk = speaker.match_score(None)
            ctx = 0.2  # TODO: caller-ID/contact/txn enrichment via init.call_id
            if init.policy_profile == "high-value-txn":
                ctx = 0.6
            final, state, action = fusion.fuse(
                init.session_id, spoof, ling, spk, ctx, pflag == "flat", init.policy_profile
            )
            if state == "high":
                action = "hold"
                alerts.emit(init.session_id, state, final, action)
                tel_action = "challenge"  # UI: show HOLD + challenge card
            else:
                tel_action = action

            fusion_bd = fusion.get_fusion_breakdown(spoof, ling, ctx, pflag == "flat")
            forensic_rep = explainability.generate_forensic_report(
                window, matched_hits, spoof, pflag
            )

            await ws.send_text(json.dumps({
                "seq": seq, "server_ts": int(time.time() * 1000), "vad": True,
                "quality": quality, "spoof_score": round(spoof, 3),
                "acoustic_risk_score": round(spoof, 3),
                "speaker_match_score": spk, "prosody_flag": pflag,
                "linguistic_score": round(ling, 3),
                "linguistic_risk_score": round(ling, 3),
                "transcript_delta": transcript_acc,
                "context_risk": ctx, "final_risk": round(final, 3),
                "final_risk_score": round(final, 3), "state": state,
                "action": tel_action, "model_ver": model_registry.model_version(),
                "policy_ver": settings.policy_ver,
                "fusion_breakdown": fusion_bd,
                "explainability": forensic_rep,
            }))

    except WebSocketDisconnect:
        return
