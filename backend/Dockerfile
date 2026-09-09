# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base
ENV UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

# system deps for audio (soundfile/libsndfile) + curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 curl \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./
COPY app ./app
COPY scripts ./scripts
RUN mkdir -p models

# mock deps (fast). For full (torch/onnx) build: --extra full
RUN uv sync --frozen --no-dev

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8000/api/v1/health || exit 1
CMD ["/srv/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
