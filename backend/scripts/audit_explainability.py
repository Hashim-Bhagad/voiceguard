"""Audit whether the explainability markers actually discriminate real from fake.

The API returns a `explainability.diagnostic_reasons` list that reads like forensic
evidence. Each claim must be checked against labelled audio, because a marker that
fires equally on genuine and synthetic speech is not an explanation -- it is a
plausible-sounding sentence attached to a verdict, which is worse than saying
nothing.

For every marker this reports the per-class distribution and how often the
associated diagnostic sentence fires on genuine vs synthetic clips.

    python scripts/audit_explainability.py --limit 60
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import audio_utils, explainability, model_registry, prosody  # noqa: E402

DEFAULT_MANIFEST = Path("/home/hashim/voice-guard/training/data/metadata.csv")


def auc(pos: list[float], neg: list[float]) -> float:
    """Probability a random spoof scores above a random bona-fide (rank AUC)."""
    if not pos or not neg:
        return float("nan")
    values = [(v, 1) for v in pos] + [(v, 0) for v in neg]
    values.sort(key=lambda t: t[0])
    ranks: dict[int, list[float]] = {}
    for index, (_, label) in enumerate(values, start=1):
        ranks.setdefault(label, []).append(index)
    n_pos, n_neg = len(pos), len(neg)
    rank_sum = sum(ranks.get(1, []))
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def describe(name: str, real: list[float], fake: list[float], span: str = "") -> None:
    a = auc(fake, real)
    verdict = "DISCRIMINATES" if abs(a - 0.5) >= 0.15 else "NO SIGNAL"
    print(f"  {name:26s} real={np.mean(real):7.3f}±{np.std(real):.3f}  "
          f"fake={np.mean(fake):7.3f}±{np.std(fake):.3f}  AUC={a:.3f}  {verdict} {span}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit", type=int, default=60, help="Clips per class")
    args = parser.parse_args()

    import csv

    manifest = Path(args.manifest)
    if not manifest.is_file():
        raise SystemExit(f"Manifest not found: {manifest}")
    # stdlib csv on purpose: the backend venv stays lean (no pandas/torch).
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows_all = [r for r in csv.DictReader(handle) if r["split"] == args.split]
    root = manifest.parent

    stats: dict[str, dict[str, list[float]]] = {
        "spoof_score": {"bonafide": [], "spoof": []},
        "jitter_pct": {"bonafide": [], "spoof": []},
        "spectral_discontinuity": {"bonafide": [], "spoof": []},
    }
    prosody_flat = {"bonafide": 0, "spoof": 0}
    reason_counts: dict[str, dict[str, int]] = {}
    totals = {"bonafide": 0, "spoof": 0}
    jitter_at_ceiling = {"bonafide": 0, "spoof": 0}

    for label in ("bonafide", "spoof"):
        rows = [r for r in rows_all if r["label"] == label][: args.limit]
        print(f"scoring {len(rows)} {label} clips from split={args.split} ...")
        for row in rows:
            path = root / row["clip_path"]
            if not path.is_file():
                continue
            audio = audio_utils.decode_audio_to_16k_mono(path.read_bytes())
            if audio.size == 0:
                continue
            spoof = float(model_registry.score_spoof(audio))
            jitter = explainability.extract_pitch_jitter(audio)
            spec = explainability.extract_spectral_discontinuity(audio)
            pflag = prosody.prosody_flag(audio)

            stats["spoof_score"][label].append(spoof)
            stats["jitter_pct"][label].append(jitter)
            stats["spectral_discontinuity"][label].append(spec)
            if pflag == "flat":
                prosody_flat[label] += 1
            if jitter >= 3.999:
                jitter_at_ceiling[label] += 1
            totals[label] += 1

            report = explainability.generate_forensic_report(
                audio_16k=audio, linguistic_hits=[], spoof_score=spoof, prosody_flag=pflag
            )
            for reason in report["diagnostic_reasons"]:
                # Bucket by the leading phrase so numbers do not fragment the key.
                key = reason.split("(")[0].split(":")[0].strip()[:64]
                reason_counts.setdefault(key, {"bonafide": 0, "spoof": 0})[label] += 1

    print("\n=== marker separation (AUC 0.5 = useless, 1.0 = perfect) ===")
    describe("spoof_score (ONNX model)", stats["spoof_score"]["bonafide"],
             stats["spoof_score"]["spoof"])
    describe("jitter_pct", stats["jitter_pct"]["bonafide"], stats["jitter_pct"]["spoof"])
    describe("spectral_discontinuity", stats["spectral_discontinuity"]["bonafide"],
             stats["spectral_discontinuity"]["spoof"])

    print("\n=== jitter saturation (estimator clips at 4.0) ===")
    for label in ("bonafide", "spoof"):
        n = totals[label] or 1
        pct = 100.0 * jitter_at_ceiling[label] / n
        print(f"  {label:9s} {jitter_at_ceiling[label]:3d}/{totals[label]:3d} clips pinned at "
              f"the 4.0 ceiling ({pct:.0f}%)")

    print("\n=== prosody 'flat' rate ===")
    for label in ("bonafide", "spoof"):
        n = totals[label] or 1
        print(f"  {label:9s} {prosody_flat[label]:3d}/{totals[label]:3d} "
              f"({100.0 * prosody_flat[label] / n:.0f}%)")

    print("\n=== how often each diagnostic sentence fires ===")
    print(f"  {'reason':64s} {'bonafide':>9s} {'spoof':>7s}  assessment")
    for key, counts in sorted(reason_counts.items(), key=lambda kv: -kv[1]["spoof"]):
        b_rate = 100.0 * counts["bonafide"] / max(1, totals["bonafide"])
        s_rate = 100.0 * counts["spoof"] / max(1, totals["spoof"])
        if b_rate >= 50 and s_rate >= 50:
            note = "FIRES ON BOTH -> misleading"
        elif b_rate > s_rate:
            note = "FIRES MORE ON GENUINE -> inverted"
        elif s_rate - b_rate >= 30:
            note = "informative"
        else:
            note = "weak"
        print(f"  {key:64s} {b_rate:8.0f}% {s_rate:6.0f}%  {note}")

    print(
        "\nAny marker flagged 'FIRES ON BOTH' or 'inverted' is stating a forensic\n"
        "conclusion the audio does not support. Those sentences should be removed or\n"
        "recalibrated before this output is shown to a reviewer."
    )


if __name__ == "__main__":
    main()
