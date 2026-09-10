from fastapi import APIRouter
from app.core.config import get_settings
from app.services.model_registry import backend_name, model_status, model_version

router = APIRouter()


@router.get("/health")
def health():
    s = get_settings()
    return {
        "status": "ok",
        "app": s.app_name,
        "model_backend": backend_name(),
        "model_ver": model_version(),
        "policy_ver": s.policy_ver,
        "retain_raw_audio": s.retain_raw_audio,
    }


@router.get("/health/model")
def health_model():
    """Prove which code path will score audio, not just which one is configured.

    Returns the resolved model path, its sha256, whether the ONNX session really
    loaded, and the declared input/output tensor contract. If
    ``inference_path`` is "heuristic" then scores are NOT coming from the neural
    model, regardless of what MODEL_BACKEND says.
    """
    return model_status()
