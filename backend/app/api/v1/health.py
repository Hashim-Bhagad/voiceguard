from fastapi import APIRouter
from app.core.config import get_settings
from app.services.model_registry import backend_name, model_version

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
