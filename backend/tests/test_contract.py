from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_fusion_thresholds():
    from app.services.fusion import fuse, get_fusion_breakdown
    f, state, _ = fuse("t1", 0.9, 0.9, None, 0.6, True, "high-value-txn")
    assert state == "high"
    f2, s2, _ = fuse("t2", 0.05, 0.05, None, 0.0, False, "standard")
    assert s2 == "low"

    bd = get_fusion_breakdown(0.8, 0.7, 0.4, True)
    assert "weights" in bd
    assert "formula_display" in bd
    assert bd["weights"]["acoustic"] == 0.55


def test_linguistic_multilingual():
    from app.services.linguistic import score_text
    # Hinglish scam
    score, hits = score_text("Turant 10 lakh transfer kar do, secret hai kisi ko mat batana")
    assert score >= 0.60
    assert "turant" in hits
    assert "transfer kar" in hits
    assert "kisi ko mat batana" in hits

    # Hindi KYC scam
    score_hi, hits_hi = score_text("आपका खाता ब्लॉक हो गया है तुरंत ओटीपी बताएं")
    assert score_hi >= 0.50

    # Safe text
    score_safe, hits_safe = score_text("Good morning, let us review the quarterly report.")
    assert score_safe <= 0.10
    assert len(hits_safe) == 0


def test_explainability_forensics():
    import numpy as np
    from app.services.explainability import generate_forensic_report
    
    # Generate 1 second synthetic tone vs pseudo-random
    t = np.linspace(0, 1.0, 16000, endpoint=False)
    synthetic_audio = 0.5 * np.sin(2 * np.pi * 220 * t)  # Pure sine wave has very uniform periods
    
    report = generate_forensic_report(synthetic_audio, ["turant", "secret"], 0.75, "flat")
    assert "jitter_pct" in report
    assert "spectral_discontinuity" in report
    assert "diagnostic_reasons" in report
    assert len(report["diagnostic_reasons"]) > 0


def test_challenge_workflow():
    from app.services.challenge import create_challenge, verify_challenge_audio
    import numpy as np
    import io
    import wave

    ch = create_challenge("session_test_123")
    assert "display_code" in ch
    assert len(ch["tokens"]) == 4

    # Create 0.5s dummy WAV audio
    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes((np.zeros(8000, dtype=np.int16)).tobytes())
    raw_wav = wav_io.getvalue()

    res = verify_challenge_audio("session_test_123", raw_wav, filename="test.wav")
    assert "result" in res
    assert "latency_ms" in res
    assert "spoof_score" in res


def test_verify_file_endpoint():
    import numpy as np
    import io
    import wave

    wav_io = io.BytesIO()
    with wave.open(wav_io, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes((np.zeros(16000, dtype=np.int16)).tobytes())
    raw_wav = wav_io.getvalue()

    r = client.post(
        "/api/v1/verify/file",
        files={"file": ("test.wav", raw_wav, "audio/wav")},
        data={"transcript": "Turant transfer kar do boss ka order hai", "policy_profile": "standard"}
    )
    assert r.status_code == 200
    data = r.json()
    assert "explainability" in data
    assert "fusion_breakdown" in data
    assert "privacy_attestation" in data
    assert data["privacy_attestation"]["zero_raw_audio_stored"] is True
    assert data["linguistic_score"] >= 0.50

