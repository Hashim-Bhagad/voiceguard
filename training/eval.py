"""Evaluate an AASIST-L checkpoint with a dev-derived operating threshold.

The headline number is the EER on the ``test`` split, whose spoof generators were
never seen in training. The threshold is taken from ``dev`` so the test set is
never used to tune anything.

Group breakdowns matter as much as the headline here. A multilingual detector
trained on Indic bona-fide plus English spoof can post an excellent overall EER
while being useless on Indic spoof, so per-language and per-generator FPR/FNR are
printed by default, and a per-language EER is computed wherever a language has
both labels present.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from torch.utils.data import DataLoader

from src.dataset import SpoofDataset, assert_no_leakage, load_metadata
from src.model import build_model

GROUP_COLUMNS = ("language", "attack_family", "generator", "source_dataset", "codec", "noise_condition")


def eer_and_threshold(labels: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    if len(np.unique(labels)) != 2:
        raise ValueError("EER requires both bonafide and spoof examples")
    fpr, tpr, thresholds = roc_curve(labels, scores)
    fnr = 1.0 - tpr
    index = int(np.nanargmin(np.abs(fpr - fnr)))
    return float((fpr[index] + fnr[index]) / 2.0), float(thresholds[index])


def resolve_device(requested: str | None) -> torch.device:
    if requested:
        return torch.device(requested)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


@torch.inference_mode()
def score_split(
    model: torch.nn.Module, df: pd.DataFrame, split: str, cfg: dict, device: torch.device
) -> pd.DataFrame:
    dataset = SpoofDataset(
        df,
        split,
        cfg["sample_rate"],
        cfg["model"]["window_samples"],
        train=False,
        cache_dir=(cfg.get("runtime") or {}).get("cache_dir"),
        seed=int(cfg.get("seed", 0)),
    )
    loader = DataLoader(
        dataset,
        batch_size=int(cfg["data"]["batch_size"]),
        shuffle=False,
        num_workers=int(cfg["data"].get("num_workers", 0)),
    )
    scores: list[float] = []
    model.eval()
    for waveform, _ in loader:
        logits = model(waveform.to(device))
        scores.extend(torch.softmax(logits.float(), dim=1)[:, 1].cpu().tolist())

    # dataset.rows is the authoritative, index-aligned view of this split.
    rows = dataset.rows.copy()
    if len(scores) != len(rows):
        raise RuntimeError(f"scored {len(scores)} clips but split has {len(rows)} rows")
    rows["score"] = scores
    rows["target"] = rows.label.map({"bonafide": 0, "spoof": 1}).astype(int)
    return rows


def print_group_metrics(rows: pd.DataFrame, threshold: float, columns: Iterable[str]) -> dict:
    prediction = (rows.score >= threshold).astype(int)
    collected: dict[str, dict] = {}
    for column in columns:
        if column not in rows or rows[column].nunique() <= 1 and len(rows[column].unique()) == 1:
            if column not in rows:
                continue
        print(f"\nby {column}:")
        per_value = {}
        for value, group in rows.groupby(column):
            group_prediction = prediction.loc[group.index]
            bona = group.target == 0
            spoof = group.target == 1
            fpr = float((group_prediction[bona] == 1).mean()) if bona.any() else float("nan")
            fnr = float((group_prediction[spoof] == 0).mean()) if spoof.any() else float("nan")
            note = ""
            if not bona.any():
                note = "  (spoof only: FPR undefined)"
            elif not spoof.any():
                note = "  (bona-fide only: FNR undefined)"
            print(
                f"  {str(value)[:28]:28s} n={len(group):5d} "
                f"FPR={fpr:.3f} FNR={fnr:.3f}{note}"
            )
            per_value[str(value)] = {"n": len(group), "fpr": fpr, "fnr": fnr}
        collected[column] = per_value
    return collected


def per_language_eer(rows: pd.DataFrame) -> dict[str, float]:
    print("\nper-language EER (only where both labels exist):")
    result: dict[str, float] = {}
    for language, group in rows.groupby("language"):
        if group.target.nunique() < 2:
            print(f"  {str(language)[:20]:20s} n={len(group):5d}  n/a (single label)")
            continue
        value, _ = eer_and_threshold(group.target.to_numpy(), group.score.to_numpy())
        result[str(language)] = value
        print(f"  {str(language)[:20]:20s} n={len(group):5d}  EER={value:.4f}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--metadata-csv", default=None, help="Defaults to the checkpoint's config")
    parser.add_argument("--eval-split", default="test")
    parser.add_argument("--threshold-split", default="dev")
    parser.add_argument("--device", default=None)
    parser.add_argument("--out-json", default=None, help="Write metrics here (default: next to ckpt)")
    parser.add_argument("--save-scores", action="store_true", help="Write per-clip scores as CSV")
    args = parser.parse_args()

    checkpoint = Path(args.ckpt).resolve()
    blob = torch.load(checkpoint, map_location="cpu", weights_only=False)
    cfg = blob["config"]
    metadata_csv = args.metadata_csv or cfg["data"]["metadata_csv"]

    df = load_metadata(metadata_csv)
    assert_no_leakage(df)

    device = resolve_device(args.device)
    threads = int((cfg.get("runtime") or {}).get("num_threads", 0) or 0)
    if threads > 0:
        torch.set_num_threads(threads)
    print(f"checkpoint={checkpoint.name} epoch={blob.get('epoch')} device={device}")

    model = build_model(cfg)
    model.load_state_dict(blob["model"], strict=True)
    model.to(device)

    calibration = score_split(model, df, args.threshold_split, cfg, device)
    dev_eer, threshold = eer_and_threshold(
        calibration.target.to_numpy(), calibration.score.to_numpy()
    )
    print(f"\n{args.threshold_split}: EER={dev_eer:.4f}  operating threshold={threshold:.5f}")

    evaluated = score_split(model, df, args.eval_split, cfg, device)
    labels = evaluated.target.to_numpy()
    scores = evaluated.score.to_numpy()
    test_eer, _ = eer_and_threshold(labels, scores)
    roc_auc = float(roc_auc_score(labels, scores))
    pr_auc = float(average_precision_score(labels, scores))
    prediction = (scores >= threshold).astype(int)
    overall_fpr = float((prediction[labels == 0] == 1).mean())
    overall_fnr = float((prediction[labels == 1] == 0).mean())

    print(
        f"{args.eval_split}: n={len(evaluated)} EER={test_eer:.4f} ROC-AUC={roc_auc:.4f} "
        f"PR-AUC={pr_auc:.4f}"
    )
    print(
        f"  at the {args.threshold_split} threshold: FPR={overall_fpr:.4f} (genuine flagged) "
        f"FNR={overall_fnr:.4f} (clones missed)"
    )

    groups = print_group_metrics(evaluated, threshold, GROUP_COLUMNS)
    language_eer = per_language_eer(evaluated)

    unseen = sorted(
        set(evaluated.loc[evaluated.label == "spoof", "generator"])
        - set(df.loc[(df.split == "train") & (df.label == "spoof"), "generator"])
    )
    print(f"\nspoof generators in {args.eval_split} that were unseen in train: {unseen}")

    # The strict number: every genuine clip vs only the spoofs whose generator never
    # appeared in train. Speaker-split sources (In-the-Wild, our clones) are unseen
    # speakers from seen tools; they count in the overall EER above, not in this one.
    strict = evaluated[(evaluated.label == "bonafide") | evaluated.generator.isin(unseen)]
    unseen_eer = None
    if strict.label.nunique() == 2:
        unseen_eer, _ = eer_and_threshold(strict.target.to_numpy(), strict.score.to_numpy())
        n_spoof = int((strict.label == "spoof").sum())
        print(f"{args.eval_split} EER on unseen generators only: {unseen_eer:.4f} "
              f"({int((strict.label == 'bonafide').sum())} genuine vs {n_spoof} unseen-generator spoofs)")
    seen = evaluated[(evaluated.label == "spoof") & ~evaluated.generator.isin(unseen)]
    if len(seen):
        print(f"  seen-tool spoofs of unseen speakers: {len(seen)} "
              f"({', '.join(sorted(seen.generator.unique()))}), "
              f"missed at the {args.threshold_split} threshold: {(seen.score < threshold).mean():.4f}")

    metrics = {
        "checkpoint": str(checkpoint),
        "epoch": blob.get("epoch"),
        "metadata_csv": str(metadata_csv),
        "threshold_split": args.threshold_split,
        "threshold": threshold,
        "dev_eer": dev_eer,
        "eval_split": args.eval_split,
        "eval_n": int(len(evaluated)),
        "eval_eer": test_eer,
        "eval_roc_auc": roc_auc,
        "eval_pr_auc": pr_auc,
        "eval_fpr_at_threshold": overall_fpr,
        "eval_fnr_at_threshold": overall_fnr,
        "per_language_eer": language_eer,
        "groups": groups,
        "unseen_generators_in_eval": unseen,
        "eval_eer_unseen_generators": unseen_eer,
    }
    out_json = Path(args.out_json) if args.out_json else checkpoint.parent / (
        f"metrics_{args.eval_split}.json"
    )
    out_json.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {out_json}")

    if args.save_scores:
        scores_csv = checkpoint.parent / f"scores_{args.eval_split}.csv"
        evaluated.drop(columns=["clip_path"]).assign(
            clip=evaluated.clip_path.map(lambda p: Path(p).name)
        ).to_csv(scores_csv, index=False)
        print(f"wrote {scores_csv}")

    single_label = [
        language for language, group in evaluated.groupby("language")
        if group.target.nunique() < 2
    ]
    if single_label:
        print(
            "\nCaveat: these languages appear with only one label in this split: "
            f"{single_label}. Their FPR/FNR is measured against nothing on the other side, so "
            "the overall EER does not tell you how the model behaves on clones in those languages."
        )


if __name__ == "__main__":
    main()
