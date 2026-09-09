"""App factory with lifespan. Routers versioned under /api/v1."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.v1 import health, verify, aux, stream


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm model registry lazily on first request (keeps cold start fast + mock boot).
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, version="0.1.0", lifespan=lifespan)
    origins = [o.strip() for o in s.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware, allow_origins=origins or ["*"],
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(verify.router, prefix="/api/v1", tags=["verify"])
    app.include_router(aux.router, prefix="/api/v1", tags=["aux"])
    app.include_router(stream.router, tags=["stream"])

    @app.get("/")
    def root():
        return {"app": s.app_name, "docs": "/docs", "health": "/api/v1/health"}

    return app


app = create_app()
