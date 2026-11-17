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



def test_spoof_operating_threshold_maps_to_half(monkeypatch):
    import numpy as np
    from app.core.config import get_settings
    from app.services import model_registry as mr

    class FakeSession:  # returns one fixed logit per window
        def __init__(self, logit):
            self.logit = logit

        def get_inputs(self):
            return [type("I", (), {"name": "waveform"})()]

        def run(self, _outputs, feeds):
            return [np.full(len(feeds["waveform"]), self.logit, dtype=np.float32)]

    threshold = 0.05393
    settings = get_settings()
    monkeypatch.setattr(settings, "model_backend", "aasist-l-onnx")
    audio = np.zeros(16000, dtype=np.float32)

    raw_logit = float(np.log(threshold / (1 - threshold)))  # model output exactly at the threshold
    monkeypatch.setattr(mr, "_try_onnx", lambda _p: FakeSession(raw_logit))

    monkeypatch.setattr(settings, "spoof_operating_threshold", 0.5)
    assert abs(mr.score_spoof(audio) - threshold) < 1e-4  # default: plain probability

    monkeypatch.setattr(settings, "spoof_operating_threshold", threshold)
    assert abs(mr.score_spoof(audio) - 0.5) < 1e-4  # shifted: threshold reads as 0.5


def test_linguistic_whole_words_and_nested_phrases():
    from app.services.linguistic import score_text, category_of, LEXICON
    # Latin terms match whole words only.
    _, hits = score_text("The spinning top was shipped to the director's hotpot stall")
    assert "pin" not in hits and "otp" not in hits
    assert "director" in hits
    # A term inside a longer matched phrase is one cue, not two.
    _, hits = score_text("Yeh baat secret rakh, abhi ke abhi")
    assert hits == ["abhi ke abhi", "secret rakh"]
    # Every lexicon term has a real category.
    for terms in LEXICON.values():
        for term in terms:
            assert category_of(term) != "General Fraud Indicator", term
    assert category_of("तुरंत") == "Urgency"


def test_explainability_categories_come_from_lexicon():
    from app.services.explainability import categorize_linguistic_hits
    cats = {c["keyword"]: c["category"] for c in categorize_linguistic_hits(["तुरंत", "authorize", "ओटीपी"])}
    assert cats == {"तुरंत": "Urgency", "authorize": "Executive Impersonation", "ओटीपी": "Financial Coercion"}


def test_spoof_segments_match_windows(monkeypatch):
    import numpy as np
    from types import SimpleNamespace
    from app.services import model_registry as mr

    class FakeSession:
        def get_inputs(self):
            return [SimpleNamespace(name="x")]

        def run(self, _outputs, feeds):
            n = feeds["x"].shape[0]
            return [np.linspace(-2.0, 2.0, n).reshape(n, 1)]

    settings = SimpleNamespace(model_backend="aasist-l-onnx", aasist_l_onnx="fake.onnx", spoof_operating_threshold=0.5)
    monkeypatch.setattr(mr, "get_settings", lambda: settings)
    monkeypatch.setattr(mr, "_try_onnx", lambda _path: FakeSession())

    audio = np.zeros(16000 * 12, dtype=np.float32)  # 12 s -> several 4.04 s windows
    score, segments = mr.score_spoof_detailed(audio)
    assert len(segments) == len(mr._window_starts(len(audio)))
    assert segments[0]["start_s"] == 0.0 and segments[-1]["end_s"] <= 12.0
    assert segments[0]["spoof_score"] < 0.5 < segments[-1]["spoof_score"]
    assert abs(score - mr.score_spoof(audio)) < 1e-9


def test_heuristic_fallback_has_no_segments(monkeypatch):
    import numpy as np
    from types import SimpleNamespace
    from app.services import model_registry as mr
    monkeypatch.setattr(mr, "get_settings", lambda: SimpleNamespace(model_backend="mock", aasist_l_onnx="", spoof_operating_threshold=0.5))
    _, segments = mr.score_spoof_detailed(np.random.default_rng(0).normal(0, 0.1, 32000).astype(np.float32))
    assert segments == []


def test_auto_language_hints_are_not_sent_to_whisper(monkeypatch):
    from types import SimpleNamespace
    from app.services import stt
    sent = {}

    class FakeClient:
        audio = SimpleNamespace(transcriptions=SimpleNamespace(create=lambda **kw: sent.update(kw) or {"text": "namaste", "language": "Hindi"}))

    monkeypatch.setattr(stt, "get_groq_client", lambda: FakeClient())
    out = stt.transcribe_audio_detailed(b"abc", "a.wav", "auto-hinglish")
    assert "language" not in sent
    assert out == {"text": "namaste", "language": "hindi", "language_source": "whisper"}
    out = stt.transcribe_audio_detailed(b"abc", "a.wav", "ta")
    assert sent["language"] == "ta" and out["language_source"] == "hint"
