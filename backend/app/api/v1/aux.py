from fastapi import APIRouter, UploadFile, File, Form
from app.schemas.contracts import EnrollRequest, POLICY_DEFAULTS
from app.services import speaker, challenge, alerts, firestore_service

router = APIRouter()


@router.post("/enroll")
def enroll(req: EnrollRequest):
    n = speaker.enroll(req.speaker_id, req.embedding)
    return {"speaker_id": req.speaker_id, "dim": n, "status": "enrolled"}


@router.get("/policy")
def policy():
    return {k: v.model_dump() for k, v in POLICY_DEFAULTS.items()}


@router.post("/challenge/create")
def challenge_create(session_id: str):
    return challenge.create_challenge(session_id)


@router.post("/challenge/verify")
def challenge_verify(session_id: str, transcript: str, spoof_score: float = 0.0):
    return challenge.verify_response(session_id, transcript, spoof_score)


@router.post("/challenge/verify-audio")
async def challenge_verify_audio(session_id: str = Form(...), file: UploadFile = File(...)):
    raw = await file.read()
    return challenge.verify_challenge_audio(session_id, raw, filename=file.filename or "response.wav")


@router.get("/sessions")
def get_sessions(limit: int = 25):
    return firestore_service.get_recent_sessions(limit_count=limit)


@router.get("/alerts")
def get_alerts(limit: int = 50):
    return firestore_service.get_recent_alerts(limit_count=limit)


@router.get("/events")
def events(n: int = 50):
    return alerts.recent(n)


@router.post("/events/emit")
def emit(session_id: str, state: str, final_risk: float, action: str):
    return alerts.emit(session_id, state, final_risk, action)
