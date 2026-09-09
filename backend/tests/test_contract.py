from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_fusion_thresholds():
    from app.services.fusion import fuse
    f, state, _ = fuse("t1", 0.9, 0.9, None, 0.6, True, "high-value-txn")
    assert state == "high"
    f2, s2, _ = fuse("t2", 0.05, 0.05, None, 0.0, False, "standard")
    assert s2 == "low"


def test_verify_file_mock():
    r = client.post("/api/v1/verify/file", files={"audio": ("x.raw", b"\x00\x01" * 8000)}, data={"policy_profile": "standard"})
    # field name is 'file'; wrong name -> 422, assert contract enforced
    assert r.status_code == 422
