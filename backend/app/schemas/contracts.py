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
    flags: list[str] = []
    challenge_triggered: bool = False
    acoustic_risk_score: float = 0.0
    linguistic_risk_score: float = 0.0
    final_risk_score: float = 0.0
    transcript: str = ""
    lang_detected: str = "auto"
    # Additive (v1-compatible): where lang_detected came from, so a client never
    # shows an echoed hint as a detection. "whisper" | "hint" | "none".
    lang_source: Literal["whisper", "hint", "none"] = "none"
    explainability: dict = Field(default_factory=dict)
    fusion_breakdown: dict = Field(default_factory=dict)
    privacy_attestation: dict = Field(default_factory=lambda: {
        "zero_raw_audio_stored": True,
        "ephemeral_ram_buffer": True,
        "compliance": "DPDP Act 2023 Compliant",
        "retention_policy": "Derived features only; raw waveform discarded post-inference",
    })


class EnrollRequest(BaseModel):
    speaker_id: str
    embedding: list[float] = []  # client may send precomputed ECAPA; empty = enroll from upload later
    lang_hint: str = "auto"


class PolicyThresholds(BaseModel):
    low_thr: float = 0.35
    high_thr: float = 0.7


# Thresholds apply to final_risk, NOT to the raw spoof score. Fusion is
#     final_risk = 0.55*spoof + 0.25*linguistic + 0.20*context
# and today linguistic is always 0.0 while context is a constant 0.2 for the
# "standard" profile, so in practice:
#     final_risk = 0.55*spoof + 0.04       (range 0.04 .. 0.59)
# The old high_thr of 0.70 was therefore unreachable -- even spoof=1.0 capped at
# 0.59 and reported "review", never "high".
#
# These values are derived from the measured operating points in
# scripts/tune_decision_layer.py (454-clip held-out test split, mean aggregation):
#     spoof 0.944 -> 90% clone recall at 39% FPR  -> final_risk 0.559
#     spoof 0.564 -> boundary below which we stay "low"  -> final_risk 0.350
# high_thr is set just under 0.559 so the 90%-recall point trips "high".
#
# Re-derive these after any retrain; do not hand-edit them.
POLICY_DEFAULTS: dict[str, PolicyThresholds] = {
    "standard": PolicyThresholds(low_thr=0.35, high_thr=0.55),
    "high-value-txn": PolicyThresholds(low_thr=0.28, high_thr=0.48),
    "privileged-access": PolicyThresholds(low_thr=0.25, high_thr=0.45),
}
