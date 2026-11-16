# VoiceGuard Backend

FastAPI streaming anti-spoofing service. It boots in `mock` mode so the mobile and web clients can use the frozen API contract before a trained model is available.

The only production acoustic model is `aasist-l-indic-v0.1.onnx`, fine-tuned in `../training/`. It runs through ONNX Runtime's CPU provider; no server GPU is required.

## Quickstart (uv)

```bash
cd backend
uv sync --extra dev
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8000
# docs: http://localhost:8000/docs
```

## Docker

```bash
cd backend
cp .env.example .env
# Keep MODEL_BACKEND=mock until the validated ONNX export has been copied.
docker compose up --build
```

## Serve AASIST-L

1. Fine-tune and validate a model with `../training/` (locally, or on a GPU via
   `../training/cloud/`). The 0.8 MB `aasist-l-indic-v0.1.onnx` is already committed.
2. For a new export, copy the `.onnx` file to `backend/models/` and point `AASIST_L_ONNX` at it.
   The XLS-R model uses the same input/output contract.
3. Set `MODEL_BACKEND=aasist-l-onnx` in `.env` and restart the backend.

The backend pads short speech buffers and keeps the most recent speech for a fixed 64,600-sample, 16 kHz AASIST-L window. It consumes the exported scalar `spoof_logit`, converts it to the exact two-class softmax spoof probability, and keeps the telemetry contract unchanged.

Raw audio is never written to disk by default (`RETAIN_RAW_AUDIO=false`).
