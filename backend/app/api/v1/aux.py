from fastapi import APIRouter
from app.schemas.contracts import EnrollRequest, POLICY_DEFAULTS
from app.services import speaker, challenge, alerts

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


@router.get("/events")
def events(n: int = 50):
    return alerts.recent(n)


@router.post("/events/emit")
def emit(session_id: str, state: str, final_risk: float, action: str):
    return alerts.emit(session_id, state, final_risk, action)
