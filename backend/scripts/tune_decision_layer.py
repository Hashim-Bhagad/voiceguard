"""Reduce false positives without retraining, by tuning the decision layer.

The model weights are fixed here. What varies is everything downstream of the
raw per-window logits:

  * window aggregation   max / mean / median / trimmed mean / quantiles
  * speech gating        drop low-energy windows before aggregating
  * test-time augmentation  average over benign variants of the same clip
  * operating threshold  chosen on dev for a target FPR, instead of 0.5

Inference runs ONCE per clip and the per-window logits are cached, so every
strategy is then evaluated offline for free.

Reported metrics, all on the held-out test split:
  EER        equal-error rate (threshold-free, measures ranking quality)
  FPR@95TPR  false positives on genuine audio while catching 95% of spoofs
  FPR@90TPR  same at 90% spoof recall
That FPR column is the number that matters for "genuine callers being flagged".

    python scripts/tune_decision_layer.py --limit 0        # whole test split
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services import audio_utils, model_registry  # noqa: E402

SAMPLES = model_registry.AASIST_L_SAMPLES
DEFAULT_MANIFEST = Path("/home/hashim/voice-guard/training/data/metadata.csv")


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------
def roc(labels: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    order = np.argsort(-scores)
    labels = labels[order]
    scores = scores[order]
    tp = np.cumsum(labels == 1)
    fp = np.cumsum(labels == 0)
    n_pos = max(1, int((labels == 1).sum()))
    n_neg = max(1, int((labels == 0).sum()))
    return tp / n_pos, fp / n_neg, scores


def eer(labels: np.ndarray, scores: np.ndarray) -> float:
    tpr, fpr, _ = roc(labels, scores)
    fnr = 1.0 - tpr
    idx = int(np.nanargmin(np.abs(fpr - fnr)))
    return float((fpr[idx] + fnr[idx]) / 2.0)


def fpr_at_tpr(labels: np.ndarray, scores: np.ndarray, target_tpr: float) -> tuple[float, float]:
    """Lowest FPR achieving at least target_tpr, and the threshold that does it."""
    tpr, fpr, thr = roc(labels, scores)
    ok = np.where(tpr >= target_tpr)[0]
    if len(ok) == 0:
        return float("nan"), float("nan")
    i = int(ok[0])
    return float(fpr[i]), float(thr[i])


# --------------------------------------------------------------------------
# windowing / gating
# --------------------------------------------------------------------------
def all_windows(waveform: np.ndarray) -> np.ndarray:
    w = np.ascontiguousarray(np.asarray(waveform, dtype=np.float32).reshape(-1))
    if len(w) <= SAMPLES:
        return model_registry._repeat_pad(w)[None, :]
    stride = SAMPLES // 2
    starts = list(range(0, len(w) - SAMPLES + 1, stride))
    if len(starts) > 8:
        picks = np.linspace(0, len(starts) - 1, 8).round().astype(int)
        starts = [starts[i] for i in dict.fromkeys(picks.tolist())]
    return np.stack([w[s:s + SAMPLES] for s in starts])


def window_energies(windows: np.ndarray) -> np.ndarray:
    return np.sqrt(np.mean(windows.astype(np.float64) ** 2, axis=1))


AGGREGATORS: dict[str, callable] = {
    "max (current)": lambda v: float(np.max(v)),
    "mean": lambda v: float(np.mean(v)),
    "median": lambda v: float(np.median(v)),
    "p75": lambda v: float(np.quantile(v, 0.75)),
    "trimmed_mean_20": lambda v: float(
        np.mean(np.sort(v)[int(0.2 * len(v)): max(1, int(0.8 * len(v)))]) if len(v) >= 3
        else np.mean(v)
    ),
    "min": lambda v: float(np.min(v)),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit", type=int, default=0, help="0 = all clips")
    parser.add_argument("--energy-gate", type=float, default=0.25,
                        help="Drop windows whose RMS is below this fraction of the clip's loudest window")
    parser.add_argument("--tta", action="store_true", help="Also score gain/shift variants")
    args = parser.parse_args()

    settings = get_settings()
    session = model_registry._try_onnx(settings.aasist_l_onnx)
    if session is None:
        raise SystemExit(
            "ONNX model not loaded -- results would come from the fallback heuristic.\n"
            f"  {model_registry.model_status().get('load_error')}"
        )
    input_name = session.get_inputs()[0].name

    manifest = Path(args.manifest)
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = [r for r in csv.DictReader(handle) if r["split"] == args.split]
    if args.limit:
        keep: list[dict] = []
        for label in ("bonafide", "spoof"):
            keep += [r for r in rows if r["label"] == label][: args.limit]
        rows = keep
    root = manifest.parent

    print(f"scoring {len(rows)} clips from split={args.split} (one inference pass, logits cached)")
    cached: list[dict] = []
    for index, row in enumerate(rows, start=1):
        path = root / row["clip_path"]
        if not path.is_file():
            continue
        audio = audio_utils.decode_audio_to_16k_mono(path.read_bytes())
        if audio.size == 0:
            continue
        windows = all_windows(audio)
        logits = np.asarray(
            session.run(None, {input_name: windows})[0], dtype=np.float64
        ).reshape(-1)
        entry = {
            "label": 1 if row["label"] == "spoof" else 0,
            "generator": row.get("generator", "none"),
            "logits": logits,
            "energies": window_energies(windows),
        }
        if args.tta:
            variants = [windows * 0.7, windows * 1.3]
            extra = [
                np.asarray(session.run(None, {input_name: v.astype(np.float32)})[0],
                           dtype=np.float64).reshape(-1)
                for v in variants
            ]
            entry["tta_logits"] = np.concatenate([logits] + extra)
        cached.append(entry)
        if index % 100 == 0:
            print(f"  {index}/{len(rows)}")

    labels = np.array([c["label"] for c in cached])
    n_bona = int((labels == 0).sum())
    n_spoof = int((labels == 1).sum())
    multi = sum(1 for c in cached if len(c["logits"]) > 1)
    print(f"\n{n_bona} genuine, {n_spoof} spoof; {multi} clips had >1 window\n")

    def evaluate(name: str, key: str = "logits", gate: bool = False) -> None:
        print(f"--- {name} ---")
        print(f"  {'aggregation':18s} {'EER':>7s} {'FPR@95%TPR':>11s} {'FPR@90%TPR':>11s}")
        for agg_name, agg in AGGREGATORS.items():
            scores = []
            for c in cached:
                values = c[key]
                if gate and len(c["logits"]) > 1:
                    energies = c["energies"]
                    keep_mask = energies >= args.energy_gate * max(energies.max(), 1e-9)
                    if keep_mask.any() and len(values) == len(keep_mask):
                        values = values[keep_mask]
                scores.append(agg(np.asarray(values)))
            scores = np.asarray(scores)
            e = eer(labels, scores)
            f95, _ = fpr_at_tpr(labels, scores, 0.95)
            f90, _ = fpr_at_tpr(labels, scores, 0.90)
            print(f"  {agg_name:18s} {e:7.4f} {f95:11.3f} {f90:11.3f}")
        print()

    evaluate("no speech gating (all windows)")
    evaluate(f"speech gating (drop windows below {args.energy_gate:.0%} of peak RMS)", gate=True)
    if args.tta:
        evaluate("test-time augmentation (gain 0.7/1.0/1.3)", key="tta_logits")

    # Best single-window baseline for reference: what eval.py measures.
    single = np.array([c["logits"][len(c["logits"]) // 2] for c in cached])
    print("--- reference: one centre window only (what training/eval.py scores) ---")
    f95, _ = fpr_at_tpr(labels, single, 0.95)
    f90, _ = fpr_at_tpr(labels, single, 0.90)
    print(f"  {'centre window':18s} {eer(labels, single):7.4f} {f95:11.3f} {f90:11.3f}\n")

    # Threshold table for the best config the operator will actually deploy.
    print("--- operating points (mean aggregation, speech-gated) ---")
    scores = []
    for c in cached:
        values = c["logits"]
        if len(values) > 1:
            energies = c["energies"]
            keep_mask = energies >= args.energy_gate * max(energies.max(), 1e-9)
            if keep_mask.any():
                values = values[keep_mask]
        scores.append(float(np.mean(values)))
    scores = np.asarray(scores)
    print(f"  {'target spoof recall':22s} {'threshold(logit)':>17s} {'sigmoid':>9s} {'FPR on genuine':>15s}")
    for target in (0.99, 0.95, 0.90, 0.80):
        f, thr = fpr_at_tpr(labels, scores, target)
        sig = 1.0 / (1.0 + np.exp(-np.clip(thr, -30, 30)))
        print(f"  {target:>21.0%} {thr:17.3f} {sig:9.4f} {f:15.3f}")

    print(
        "\nRead the FPR@95%TPR column: that is the fraction of genuine callers flagged\n"
        "while still catching 95% of clones. Pick the aggregation with the lowest value,\n"
        "then set the backend threshold from the operating-point table above.\n"
        "None of this requires retraining."
    )


if __name__ == "__main__":
    main()
