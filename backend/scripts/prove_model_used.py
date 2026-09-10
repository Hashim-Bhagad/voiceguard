"""Prove that audio posted to the running API actually went through the ONNX model.

A config flag saying "aasist-l-onnx" is not evidence. This script establishes it
three independent ways:

  1. /api/v1/health/model must report onnx_session_loaded=true and give the
     sha256 of the file that is loaded.
  2. The API's spoof_score must match a direct, in-process ONNX run on the same
     file to within float tolerance. A heuristic fallback cannot coincidentally
     reproduce the model's logits.
  3. A single flipped-sign copy of the audio must move the score the way the
     model does, not the way an energy heuristic would (RMS and variance are
     sign-invariant, so the fallback returns an identical score while a real
     neural net does not).

    python scripts/prove_model_used.py sample.wav --url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import wave
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import audio_utils, model_registry  # noqa: E402


def post_verify(url: str, path: Path) -> dict:
    import httpx

    with path.open("rb") as handle:
        files = {"file": (path.name, handle, "audio/wav")}
        data = {"policy_profile": "standard", "caller_id": "proof"}
        response = httpx.post(f"{url}/api/v1/verify/file", files=files, data=data, timeout=180.0)
    response.raise_for_status()
    return response.json()


def write_wav(samples: np.ndarray, rate: int = 16000) -> bytes:
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return buffer.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.is_file():
        raise SystemExit(f"not found: {path}")

    import httpx

    passed = 0
    failed = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if ok:
            passed += 1
            print(f"  PASS  {name} {detail}")
        else:
            failed += 1
            print(f"  FAIL  {name} {detail}")

    print("=== 1. server reports a real, loaded ONNX session ===")
    status = httpx.get(f"{args.url}/api/v1/health/model", timeout=30.0).json()
    print(json.dumps({k: status[k] for k in (
        "configured_backend", "model_path_absolute", "model_file_exists",
        "onnx_session_loaded", "inference_path", "reported_model_ver", "load_error",
    ) if k in status}, indent=2))
    check("inference_path is aasist-l-onnx", status.get("inference_path") == "aasist-l-onnx")
    check("onnx session loaded", status.get("onnx_session_loaded") is True)
    check("no load error", status.get("load_error") in (None, ""))
    server_sha = status.get("model_sha256")
    print(f"  server model sha256: {server_sha}")

    local_path = BACKEND_ROOT / status["model_path"]
    if local_path.is_file():
        import hashlib

        digest = hashlib.sha256(local_path.read_bytes()).hexdigest()
        check("sha256 matches the file on disk", digest == server_sha)

    print("\n=== 2. API score reproduces a direct in-process ONNX run ===")
    api = post_verify(args.url, path)
    api_score = float(api["spoof_score"])
    audio = audio_utils.decode_audio_to_16k_mono(path.read_bytes())
    direct_score = float(model_registry.score_spoof(audio))
    print(f"  API spoof_score    : {api_score:.12f}")
    print(f"  direct ONNX score  : {direct_score:.12f}")
    print(f"  absolute difference: {abs(api_score - direct_score):.3e}")
    check("scores match to 1e-6", abs(api_score - direct_score) < 1e-6)
    check("API reports the neural model_ver",
          api.get("model_ver") == status.get("reported_model_ver"),
          f"({api.get('model_ver')})")

    print("\n=== 3. sign flip: distinguishes the model from an energy heuristic ===")
    # RMS and variance are invariant to a sign flip, so the development fallback
    # returns a bit-identical score. A neural net does not.
    flipped = write_wav(-audio)
    tmp = Path("/tmp/vg_proof_flipped.wav")
    tmp.write_bytes(flipped)
    flipped_api = post_verify(args.url, tmp)
    flipped_score = float(flipped_api["spoof_score"])
    print(f"  original score : {api_score:.12f}")
    print(f"  sign-flipped   : {flipped_score:.12f}")
    delta = abs(api_score - flipped_score)
    print(f"  delta          : {delta:.3e}")
    check("sign flip changed the score (heuristic would not)", delta > 1e-9,
          "-> a pure RMS/variance fallback would give delta exactly 0")
    tmp.unlink(missing_ok=True)

    print(f"\n{passed} passed, {failed} failed")
    if failed:
        print("At least one proof failed: do NOT treat these scores as neural model output.")
    else:
        print("Verified: audio posted to this server is scored by the exported AASIST-L ONNX model.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
