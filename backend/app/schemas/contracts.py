"""FROZEN v1 streaming + REST contract. Do not rename fields — bump version instead."""
from typing import Literal
from pydantic import BaseModel, Field

PolicyProfile = Literal["standard", "high-value-txn", "privileged-access"]
RiskState = Literal["insufficient", "low", "review", "high"]
RiskAction = Literal["continue", "verify", "hold", "challenge"]


class InitMessage(BaseModel):
    type: Literal["init"] = "init"
    session_id: str
    sample_rate: int = 16000
    channels: int = 1
    codec_hint: str = "unknown"
    lang_hint: str = "auto"
    call_id: str | None = None
    policy_profile: PolicyProfile = "standard"


class FrameMeta(BaseModel):
    type: Literal["frame"] = "frame"
    seq: int
    capture_ts: int


class Telemetry(BaseModel):
    seq: int
    server_ts: int
    vad: bool = True
    quality: Literal["ok", "noisy", "low-band", "insufficient"] = "ok"
    spoof_score: float = Field(ge=0, le=1, default=0.0)
    speaker_match_score: float | None = Field(ge=0, le=1, default=None)
    prosody_flag: Literal["flat", "normal", "unknown"] = "unknown"
    linguistic_score: float = Field(ge=0, le=1, default=0.0)
    transcript_delta: str = ""
    context_risk: float = Field(ge=0, le=1, default=0.0)
    final_risk: float = Field(ge=0, le=1, default=0.0)
    state: RiskState = "insufficient"
    action: RiskAction = "continue"
    model_ver: str = "mock-v0.1"
    policy_ver: str = "p1"


class VerifyResponse(Telemetry):
    session_id: str = ""
    segments: list[dict] = []


class EnrollRequest(BaseModel):
    speaker_id: str
    embedding: list[float] = []  # client may send precomputed ECAPA; empty = enroll from upload later
    lang_hint: str = "auto"


class PolicyThresholds(BaseModel):
    low_thr: float = 0.35
    high_thr: float = 0.7


POLICY_DEFAULTS: dict[str, PolicyThresholds] = {
    "standard": PolicyThresholds(low_thr=0.35, high_thr=0.70),
    "high-value-txn": PolicyThresholds(low_thr=0.25, high_thr=0.55),
    "privileged-access": PolicyThresholds(low_thr=0.20, high_thr=0.50),
}
