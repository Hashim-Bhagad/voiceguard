"""Score arbitrary audio files with an exported VoiceGuard ONNX model.

Use this to check real-world behaviour on audio that never went through the
training pipeline: your own phone recordings, WhatsApp voice notes, podcast or
YouTube clips, clones you generate with a TTS service, and so on.

Any format ffmpeg can read works (wav, mp3, m4a, ogg/opus, flac, mp4, ...).
Long files are scored exactly as the backend scores an upload: up to 8 evenly
spaced 4.04 s windows with 50% overlap, averaged in logit space
(backend/app/services/model_registry.py).

Labels are optional and come from folder names anywhere in the path:

    my_tests/
      real/hindi/call1.m4a        -> bonafide, group "hindi"
      real/tamil/voice_note.ogg   -> bonafide, group "tamil"
      fake/elevenlabs/clip.mp3    -> spoof,    group "elevenlabs"
      fake/sarvam_bulbul/x.wav    -> spoof,    group "sarvam_bulbul"
      unsorted/whatever.wav       -> unlabelled, scored only

real / bonafide / genuine / human mark genuine audio; fake / spoof / clone /
deepfake / synthetic mark AI audio. The folder right below that is the group,
so you get one row per language, speaker or TTS system.

    python scripts/score_audio.py my_tests/ --onnx outputs/xlsr_aasist/xlsr-aasist-indic-v0.1.onnx
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16_000
WINDOW = 64_600  # 4.04 s, the model's fixed input
MAX_SECONDS = 600  # decode at most 10 minutes per file
AUDIO_EXTS = {
    ".wav", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".oga", ".flac", ".webm",
    ".mp4", ".mkv", ".mov", ".wma", ".amr", ".3gp", ".caf", ".aiff", ".aif",
}
BONAFIDE_NAMES = {"real", "bonafide", "bona-fide", "bona_fide", "genuine", "human", "live"}
SPOOF_NAMES = {"fake", "spoof", "clone", "cloned", "deepfake", "synthetic", "ai", "tts"}


# --- audio ------------------------------------------------------------------

def decode(path: Path) -> np.ndarray:
    """Decode any ffmpeg-readable file to mono float32 at 16 kHz."""
    cmd = [
        "ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-t", str(MAX_SECONDS),
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace").strip() or "ffmpeg failed")
    return np.frombuffer(proc.stdout, dtype=np.float32).copy()


def repeat_pad(wav: np.ndarray, samples: int = WINDOW) -> np.ndarray:
    """Tile a short clip up to the window, as training and the backend do."""
    if len(wav) >= samples:
        return wav[:samples]
    return np.tile(wav, math.ceil(samples / max(1, len(wav))))[:samples].astype(np.float32)


def windows(wav: np.ndarray, max_windows: int = 8) -> np.ndarray:
    """Same windowing as backend/app/services/model_registry.py:_aasist_windows."""
    if len(wav) <= WINDOW:
        return repeat_pad(wav)[None, :]
    starts = list(range(0, len(wav) - WINDOW + 1, WINDOW // 2))
    if len(starts) > max_windows:
        picks = np.linspace(0, len(starts) - 1, max_windows).round().astype(int)
        starts = [starts[i] for i in dict.fromkeys(picks.tolist())]
    return np.stack([wav[s:s + WINDOW] for s in starts])


# --- labels -----------------------------------------------------------------

def label_and_group(path: Path, root: Path) -> tuple[str, str]:
    parts = [p.lower() for p in path.relative_to(root).parts[:-1]] if path != root else []
    for i, part in enumerate(parts):
        label = "bonafide" if part in BONAFIDE_NAMES else "spoof" if part in SPOOF_NAMES else None
        if label:
            group = parts[i + 1] if i + 1 < len(parts) else "(all)"
            return label, group
    return "unlabelled", parts[0] if parts else "(root)"


def collect(paths: list[str]) -> list[tuple[Path, Path]]:
    files = []
    for raw in paths:
        p = Path(raw).expanduser().resolve()
        if p.is_dir():
            files += [(f, p) for f in sorted(p.rglob("*")) if f.suffix.lower() in AUDIO_EXTS]
        elif p.is_file():
            files.append((p, p.parent))
        else:
            sys.exit(f"not found: {raw}")
    if not files:
        sys.exit("no audio files found (extensions: " + ", ".join(sorted(AUDIO_EXTS)) + ")")
    return files


# --- metrics ----------------------------------------------------------------

def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def eer(labels: np.ndarray, scores: np.ndarray) -> float:
    from sklearn.metrics import roc_curve

    fpr, tpr, _ = roc_curve(labels, scores)
    fnr = 1 - tpr
    i = int(np.nanargmin(np.abs(fnr - fpr)))
    return float((fpr[i] + fnr[i]) / 2)


def default_threshold(onnx_path: Path) -> tuple[float, str]:
    """Use the dev threshold saved by eval.py next to the model, if there is one."""
    metrics = onnx_path.parent / "metrics_test.json"
    if metrics.is_file():
        return float(json.loads(metrics.read_text())["threshold"]), f"dev threshold from {metrics.name}"
    return 0.5, "0.5 (no metrics_test.json next to the model)"


def report(rows: list[dict], threshold: float) -> None:
    labelled = [r for r in rows if r["label"] != "unlabelled"]
    print(f"\n{'group':28s} {'label':10s} {'n':>4s}  {'flagged as AI':>13s}  {'median score':>12s}")
    keys = sorted({(r["label"], r["group"]) for r in rows})
    for label, group in keys:
        sel = [r for r in rows if r["label"] == label and r["group"] == group]
        flagged = sum(r["verdict"] == "AI" for r in sel)
        med = float(np.median([r["score"] for r in sel]))
        print(f"{group[:28]:28s} {label:10s} {len(sel):4d}  {flagged:4d} ({flagged / len(sel):5.1%})  {med:12.4f}")

    real = [r for r in labelled if r["label"] == "bonafide"]
    fake = [r for r in labelled if r["label"] == "spoof"]
    if real:
        fp = sum(r["verdict"] == "AI" for r in real)
        print(f"\nreal clips wrongly flagged as AI: {fp}/{len(real)} ({fp / len(real):.1%})")
    if fake:
        fn = sum(r["verdict"] == "real" for r in fake)
        print(f"AI clips missed (passed as real): {fn}/{len(fake)} ({fn / len(fake):.1%})")
    if real and fake:
        y = np.array([r["label"] == "spoof" for r in labelled], dtype=int)
        s = np.array([r["score"] for r in labelled])
        from sklearn.metrics import roc_auc_score

        print(f"EER on this data: {eer(y, s):.2%}   ROC-AUC: {roc_auc_score(y, s):.4f}")
    if len(labelled) < 50:
        print("note: with fewer than ~50 labelled clips per side these rates swing a lot; "
              "treat them as a smoke test, not a benchmark.")


# --- main -------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="audio files or folders (searched recursively)")
    ap.add_argument("--onnx", required=True, help="exported model, e.g. xlsr-aasist-indic-v0.1.onnx")
    ap.add_argument("--threshold", type=float, help="spoof probability above which a clip is AI "
                    "(default: the dev threshold in metrics_test.json next to the model, else 0.5)")
    ap.add_argument("--agg", choices=["mean", "max"], default="mean",
                    help="how window scores combine into one clip score (backend default: mean)")
    ap.add_argument("--max-windows", type=int, default=8)
    ap.add_argument("--threads", type=int, default=4, help="CPU threads for onnxruntime")
    ap.add_argument("--out", default="scores_real_world.csv")
    args = ap.parse_args()

    import onnxruntime as ort

    onnx_path = Path(args.onnx).expanduser().resolve()
    threshold, source = (args.threshold, "--threshold") if args.threshold is not None else default_threshold(onnx_path)
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = args.threads
    opts.inter_op_num_threads = 1
    providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in ort.get_available_providers()]
    session = ort.InferenceSession(str(onnx_path), opts, providers=providers)
    input_name = session.get_inputs()[0].name
    print(f"model: {onnx_path.name} on {session.get_providers()[0]}")
    print(f"threshold: {threshold:.5f} ({source}); clip score = {args.agg} over up to {args.max_windows} windows")

    rows = []
    files = collect(args.paths)
    for n, (path, root) in enumerate(files, 1):
        label, group = label_and_group(path, root)
        try:
            wav = decode(path)
            if len(wav) < SAMPLE_RATE // 2:
                raise RuntimeError("shorter than 0.5 s")
        except RuntimeError as exc:
            print(f"[{n}/{len(files)}] skip {path.name}: {exc}")
            continue
        batch = windows(wav, args.max_windows)
        logits = np.concatenate([session.run(None, {input_name: batch[i:i + 4]})[0].reshape(-1)
                                 for i in range(0, len(batch), 4)])
        clip_logit = float(logits.max() if args.agg == "max" else logits.mean())
        score = sigmoid(clip_logit)
        verdict = "AI" if score >= threshold else "real"
        rows.append({
            "file": str(path), "label": label, "group": group, "seconds": round(len(wav) / SAMPLE_RATE, 2),
            "windows": len(batch), "score": round(score, 6), "max_window_score": round(sigmoid(float(logits.max())), 6),
            "verdict": verdict,
        })
        mark = "" if label == "unlabelled" else (" ok" if (verdict == "AI") == (label == "spoof") else " WRONG")
        print(f"[{n}/{len(files)}] {score:.4f} {verdict:4s} {label:10s} {path.name}{mark}")

    if not rows:
        sys.exit("nothing could be scored")
    with open(args.out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report(rows, threshold)
    print(f"\nwrote {os.path.abspath(args.out)}")


if __name__ == "__main__":
    main()
