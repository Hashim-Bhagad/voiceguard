"""Score a .wav (or any audio file) with the exported AASIST-L ONNX model.

Standalone: no Groq, no Firestore, no server. Uses the same
app.services.model_registry code path the API uses, so what you see here is what
the endpoint will produce.

    python scripts/detect_wav.py sample.wav
    python scripts/detect_wav.py a.wav b.wav --json
    python scripts/detect_wav.py clip.wav --threshold 0.5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import numpy as np  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services import audio_utils, model_registry  # noqa: E402


def verdict(score: float, threshold: float) -> str:
    if score >= threshold:
        return "LIKELY AI-CLONED"
    return "likely genuine"


def band(score: float) -> str:
    if score >= 0.80:
        return "high"
    if score >= 0.50:
        return "elevated"
    if score >= 0.25:
        return "low-moderate"
    return "low"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", help="Audio files to score")
    parser.add_argument(
        "--threshold", type=float, default=0.5,
        help="Decision threshold on the spoof score. Calibrate this on your own "
             "dev split (training/eval.py prints the equal-error threshold).",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    args = parser.parse_args()

    settings = get_settings()
    backend = settings.model_backend
    onnx_path = BACKEND_ROOT / settings.aasist_l_onnx

    if backend != "aasist-l-onnx":
        print(
            f"MODEL_BACKEND is {backend!r}, not 'aasist-l-onnx'.\n"
            "Scores below would come from the development heuristic, NOT the model.\n"
            "Set MODEL_BACKEND=aasist-l-onnx in backend/.env first.",
            file=sys.stderr,
        )
        sys.exit(2)
    if not onnx_path.is_file():
        print(f"Model file missing: {onnx_path}", file=sys.stderr)
        sys.exit(2)

    if not args.json:
        print(f"model    : {onnx_path.name} ({model_registry.model_version()})")
        print(f"threshold: {args.threshold}\n")

    results = []
    for name in args.files:
        path = Path(name)
        if not path.is_file():
            print(f"  {name}: NOT FOUND", file=sys.stderr)
            continue
        raw = path.read_bytes()
        started = time.perf_counter()
        audio = audio_utils.decode_audio_to_16k_mono(raw)
        decode_ms = (time.perf_counter() - started) * 1000.0

        if audio.size == 0:
            print(f"  {path.name}: could not decode audio", file=sys.stderr)
            continue

        started = time.perf_counter()
        score = float(model_registry.score_spoof(audio))
        infer_ms = (time.perf_counter() - started) * 1000.0

        windows = model_registry._aasist_windows(audio).shape[0]
        record = {
            "file": str(path),
            "duration_s": round(len(audio) / 16000.0, 2),
            "windows_scored": windows,
            "spoof_score": round(score, 4),
            "verdict": verdict(score, args.threshold),
            "confidence_band": band(score),
            "decode_ms": round(decode_ms, 1),
            "inference_ms": round(infer_ms, 1),
        }
        results.append(record)

        if not args.json:
            print(f"  {path.name}")
            print(f"    duration    : {record['duration_s']} s "
                  f"({windows} window{'s' if windows != 1 else ''} scored)")
            print(f"    spoof score : {record['spoof_score']:.4f}  ({record['confidence_band']})")
            print(f"    verdict     : {record['verdict']}")
            print(f"    timing      : decode {record['decode_ms']} ms, "
                  f"inference {record['inference_ms']} ms")
            print()

    if args.json:
        print(json.dumps(results, indent=2))

    if not args.json and results:
        print(
            "Interpretation: the score is this model's spoof evidence, not a calibrated\n"
            "probability. This checkpoint was fine-tuned on ENGLISH data only "
            "(dev EER 13.5%\n"
            "on one unseen TTS family), so treat Hindi or other non-English audio as\n"
            "out of distribution -- it has no demonstrated skill there yet."
        )


if __name__ == "__main__":
    main()
