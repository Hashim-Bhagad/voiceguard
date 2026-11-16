"""Render the figures used in the README from a finished run.

  python scripts/plot_results.py --run-dir outputs/aasist_l_indic --out-dir ../docs/images

Inputs (all written by the training pipeline):
  history.csv        train_aasist_l.py, one row per epoch
  scores_test.csv    eval.py --save-scores, one row per test clip
  metrics_test.json  eval.py, optional; adds the dev threshold to the score plot

Outputs: training_curve.png, roc_test.png, score_distribution.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import roc_auc_score, roc_curve  # noqa: E402

GENUINE = "#3BA88F"
SPOOF = "#E0725F"
INK = "#1F2A2E"
MUTED = "#6B7B80"


def style(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED)
    ax.grid(alpha=0.25)


def training_curve(history: pd.DataFrame, out: Path) -> None:
    fig, loss_ax = plt.subplots(figsize=(7, 3.6), dpi=160)
    loss_ax.plot(history.epoch, history.train_loss, marker="o", color=INK, label="train loss")
    loss_ax.set_xlabel("epoch")
    loss_ax.set_ylabel("train loss (cross-entropy)")
    style(loss_ax)
    eer_ax = loss_ax.twinx()
    eer_ax.plot(history.epoch, history.dev_eer * 100, marker="s", color=SPOOF, label="dev EER")
    eer_ax.set_ylabel("dev EER (%)", color=SPOOF)
    eer_ax.tick_params(colors=SPOOF)
    for side in ("top", "left"):
        eer_ax.spines[side].set_visible(False)
    best = history.loc[history.dev_eer.idxmin()]
    eer_ax.annotate(f"best {best.dev_eer:.1%}", (best.epoch, best.dev_eer * 100),
                    textcoords="offset points", xytext=(8, -14), color=SPOOF, fontsize=9)
    loss_ax.set_xticks(history.epoch)
    lines = loss_ax.get_lines() + eer_ax.get_lines()
    loss_ax.legend(lines, [line.get_label() for line in lines], frameon=False, loc="upper right")
    loss_ax.set_title("Fine-tuning AASIST-L", loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def roc(scores: pd.DataFrame, out: Path) -> None:
    fpr, tpr, _ = roc_curve(scores.target, scores.score)
    fnr = 1 - tpr
    i = int(np.nanargmin(np.abs(fpr - fnr)))
    eer = (fpr[i] + fnr[i]) / 2
    auc = roc_auc_score(scores.target, scores.score)
    fig, ax = plt.subplots(figsize=(4.4, 4.2), dpi=160)
    ax.plot(fpr, tpr, color=INK, lw=2, label=f"AASIST-L fine-tuned (AUC {auc:.3f})")
    ax.plot([0, 1], [0, 1], ls="--", color=MUTED, lw=1, label="chance")
    ax.scatter([fpr[i]], [tpr[i]], color=SPOOF, zorder=3, label=f"EER {eer:.1%}")
    ax.set_xlabel("false positive rate (genuine flagged)")
    ax.set_ylabel("true positive rate (clones caught)")
    ax.set_title("Test set, unseen TTS generators", loc="left", color=INK, fontsize=10)
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    style(ax)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def distribution(scores: pd.DataFrame, threshold: float | None, out: Path) -> None:
    logit = np.log(np.clip(scores.score, 1e-6, 1 - 1e-6) / np.clip(1 - scores.score, 1e-6, 1))
    bins = np.linspace(np.percentile(logit, 0.5), np.percentile(logit, 99.5), 40)
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=160)
    ax.hist(logit[scores.target == 0], bins=bins, alpha=0.75, color=GENUINE, label="genuine")
    ax.hist(logit[scores.target == 1], bins=bins, alpha=0.75, color=SPOOF, label="spoof")
    if threshold is not None:
        t = np.log(threshold / (1 - threshold))
        ax.axvline(t, color=INK, ls="--", lw=1)
        ax.annotate("dev threshold", (t, ax.get_ylim()[1] * 0.92), xytext=(4, 0),
                    textcoords="offset points", fontsize=8, color=INK)
    ax.set_xlabel("spoof logit (positive = more spoof-like)")
    ax.set_ylabel("clips")
    ax.legend(frameon=False)
    ax.set_title("Score distribution on the test set", loc="left", color=INK)
    style(ax)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", default="outputs/aasist_l_indic")
    parser.add_argument("--scores", default=None, help="Defaults to <run-dir>/scores_test.csv")
    parser.add_argument("--metrics", default=None, help="Defaults to <run-dir>/metrics_test.json")
    parser.add_argument("--out-dir", default=None, help="Defaults to <run-dir>/figures")
    args = parser.parse_args()

    run = Path(args.run_dir)
    out_dir = Path(args.out_dir) if args.out_dir else run / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    history_csv = run / "history.csv"
    if history_csv.is_file():
        training_curve(pd.read_csv(history_csv), out_dir / "training_curve.png")
        print(f"wrote {out_dir / 'training_curve.png'}")

    scores_csv = Path(args.scores) if args.scores else run / "scores_test.csv"
    if not scores_csv.is_file():
        raise SystemExit(f"{scores_csv} not found; run eval.py --save-scores first")
    scores = pd.read_csv(scores_csv)
    metrics_json = Path(args.metrics) if args.metrics else run / "metrics_test.json"
    threshold = json.loads(metrics_json.read_text())["threshold"] if metrics_json.is_file() else None

    roc(scores, out_dir / "roc_test.png")
    distribution(scores, threshold, out_dir / "score_distribution.png")
    print(f"wrote {out_dir / 'roc_test.png'} and {out_dir / 'score_distribution.png'}")


if __name__ == "__main__":
    main()
