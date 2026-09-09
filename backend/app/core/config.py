"""Central config via env. No secrets committed."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "voiceguard-backend"
    app_env: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8000

    model_backend: str = "mock"  # mock | aasist-l-onnx
    model_dir: str = "./models"
    aasist_l_onnx: str = "models/aasist-l-indic-v0.1.onnx"
    model_ver: str = "mock-v0.1"
    policy_ver: str = "p1"

    cors_origins: str = "http://localhost:5173,http://localhost:19006"
    retain_raw_audio: bool = False
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
