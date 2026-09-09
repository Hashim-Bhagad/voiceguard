"""Evaluate an AASIST-L checkpoint using a dev-derived operating threshold."""
from __future__ import annotations

import argparse
from collections.abc import Iterable

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from torch.utils.data import DataLoader

from src.dataset import SpoofDataset, assert_no_leakage, load_metadata
from src.model import build_model


def eer_and_threshold(labels: np.ndarray, scores: np.ndarray) -> tuple[float, float]:
    if len(np.unique(labels)) != 2:
        raise ValueError("EER requires both bonafide and spoof examples")
    fpr, tpr, thresholds = roc_curve(labels, scores)
    fnr = 1.0 - tpr
    index = np.nanargmin(np.abs(fpr - fnr))
    return float((fpr[index] + fnr[index]) / 2.0), float(thresholds[index])


@torch.inference_mode()
def score_split(model: torch.nn.Module, df: pd.DataFrame, split: str, cfg: dict, device: torch.device) -> pd.DataFrame:
    rows = df[df.split == split].reset_index(drop=True)
    loader = DataLoader(
        SpoofDataset(df, split, cfg["sample_rate"], cfg["model"]["window_samples"]),
        batch_size=int(cfg["data"]["batch_size"]),
        shuffle=False,
    )
    scores: list[float] = []
    model.eval()
    for waveform, _ in loader:
        logits = model(waveform.to(device))
        scores.extend(torch.softmax(logits, dim=1)[:, 1].cpu().tolist())
    rows["score"] = scores
    rows["target"] = rows.label.map({"bonafide": 0, "spoof": 1})
    return rows


def print_group_metrics(rows: pd.DataFrame, threshold: float, columns: Iterable[str]) -> None:
    prediction = (rows.score >= threshold).astype(int)
    for column in columns:
        if column not in rows:
            continue
        print(f"\nby {column}:")
        for value, group in rows.groupby(column):
            group_prediction = prediction.loc[group.index]
            bona = group.target == 0
            spoof = group.target == 1
            fpr = float((group_prediction[bona] == 1).mean()) if bona.any() else float("nan")
            fnr = float((group_prediction[spoof] == 0).mean()) if spoof.any() else float("nan")
            print(f"  {value}: n={len(group):4d} FPR={fpr:.3f} FNR={fnr:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--metadata-csv", default="data/metadata.csv")
    parser.add_argument("--eval-split", default="test")
    parser.add_argument("--threshold-split", default="dev")
    args = parser.parse_args()

    blob = torch.load(args.ckpt, map_location="cpu")
    cfg = blob["config"]
    df = load_metadata(args.metadata_csv)
    assert_no_leakage(df)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(cfg)
    model.load_state_dict(blob["model"], strict=True)
    model.to(device)

    calibration = score_split(model, df, args.threshold_split, cfg, device)
    _, threshold = eer_and_threshold(calibration.target.to_numpy(), calibration.score.to_numpy())
    evaluated = score_split(model, df, args.eval_split, cfg, device)
    labels, scores = evaluated.target.to_numpy(), evaluated.score.to_numpy()
    value_eer, _ = eer_and_threshold(labels, scores)
    print(f"threshold from {args.threshold_split}={threshold:.5f}")
    print(f"{args.eval_split} EER={value_eer:.4f} ROC-AUC={roc_auc_score(labels, scores):.4f} PR-AUC={average_precision_score(labels, scores):.4f}")
    print_group_metrics(evaluated, threshold, ("language", "attack_family", "generator", "codec", "noise_condition"))


if __name__ == "__main__":
    main()
