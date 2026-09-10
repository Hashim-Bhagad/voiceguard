"""Compare the ORIGINAL ClovaAI AASIST-L weights against our fine-tune.

Motivation: the released AASIST-L.pth was trained on ASVspoof 2019 LA (~25k
utterances, 19 attack types). Our fine-tune saw 1108 clips from 3 generators and
its best dev epoch was epoch 1. It is entirely possible that fine-tuning made
things worse, and the honest way to find out is to measure both on the same
held-out split.

Label polarity matters and the two codebases disagree:
    upstream ClovaAI  data_utils.genSpoof_list:  1 = bonafide, 0 = spoof
    this project      src/dataset.VALID_LABELS:  0 = bonafide, 1 = spoof
so a checkpoint's spoof logit is logits[:,1]-logits[:,0] under OUR convention and
logits[:,0]-logits[:,1] under UPSTREAM's. This script reports BOTH for every
checkpoint, so the correct orientation is an observation rather than an assumption.
An EER near 0.5 means no signal; near 0 means correct polarity; near 1 means the
polarity is flipped.

    python eval_pretrained.py --split test
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
import yaml

from src.dataset import SpoofDataset, load_metadata
from src.model import build_model

TRAINING_ROOT = Path(__file__).resolve().parent


def eer_from_scores(labels: np.ndarray, scores: np.ndarray) -> float:
    """labels: 1 = spoof. scores: higher = more spoof-like."""
    order = np.argsort(-scores)
    lab = labels[order]
    tp = np.cumsum(lab == 1) / max(1, int((lab == 1).sum()))
    fp = np.cumsum(lab == 0) / max(1, int((lab == 0).sum()))
    fn = 1.0 - tp
    idx = int(np.nanargmin(np.abs(fp - fn)))
    return float((fp[idx] + fn[idx]) / 2.0)


def collect_logits(model: torch.nn.Module, loader, device: str) -> tuple[np.ndarray, np.ndarray]:
    both, labels = [], []
    with torch.inference_mode():
        for waveform, label in loader:
            out = model(waveform.to(device)).float().cpu().numpy()
            both.append(out)
            labels.append(label.numpy())
    return np.concatenate(labels), np.concatenate(both)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="configs/aasist_l.yaml")
    parser.add_argument("--split", default="test")
    parser.add_argument("--pretrained", default="third_party/aasist/models/weights/AASIST-L.pth")
    parser.add_argument("--finetuned", default="outputs/aasist_l_indic/best.pt")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()

    torch.set_num_threads(args.threads)
    with open(args.config, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)

    frame = load_metadata(cfg["data"]["metadata_csv"])
    dataset = SpoofDataset(
        frame,
        split=args.split,
        sample_rate=cfg["sample_rate"],
        window_samples=cfg["model"]["window_samples"],
        train=False,
        cache_dir=cfg["runtime"].get("cache_dir"),
        seed=cfg.get("seed", 0),
    )
    loader = torch.utils.data.DataLoader(
        dataset, batch_size=args.batch_size, shuffle=False, num_workers=2
    )
    rows = dataset.rows
    print(f"split={args.split}  clips={len(dataset)}  "
          f"spoof={int((rows['label'] == 'spoof').sum())}  "
          f"bonafide={int((rows['label'] == 'bonafide').sum())}\n")

    checkpoints: list[tuple[str, Path, str]] = [
        ("ORIGINAL AASIST-L (ASVspoof19 LA, no fine-tune)", Path(args.pretrained), "raw"),
        ("OUR fine-tune (best.pt, epoch 1)", Path(args.finetuned), "ckpt"),
    ]

    results: dict[str, dict[str, float]] = {}
    for name, path, kind in checkpoints:
        if not path.is_file():
            print(f"-- {name}: MISSING at {path}, skipped\n")
            continue
        model = build_model(cfg)
        if kind == "raw":
            missing, unexpected = model.load_pretrained(path)
            print(f"-- {name}\n   {path}\n   missing={len(missing)} unexpected={len(unexpected)}")
            if missing or unexpected:
                print("   WARNING: state dict did not match cleanly")
        else:
            blob = torch.load(path, map_location="cpu", weights_only=False)
            model.load_state_dict(blob["model"], strict=True)
            print(f"-- {name}\n   {path}\n   epoch={blob.get('epoch')} "
                  f"dev_eer={blob.get('dev_eer')}")
        model.eval()

        labels, logits = collect_logits(model, loader, "cpu")
        ours = logits[:, 1] - logits[:, 0]        # this project's polarity
        upstream = logits[:, 0] - logits[:, 1]    # ClovaAI's polarity
        eer_ours = eer_from_scores(labels, ours)
        eer_upstream = eer_from_scores(labels, upstream)
        results[name] = {"ours": eer_ours, "upstream": eer_upstream}
        print(f"   EER with OUR polarity      (logits[:,1]-logits[:,0]): {eer_ours:.4f}")
        print(f"   EER with UPSTREAM polarity (logits[:,0]-logits[:,1]): {eer_upstream:.4f}")
        print(f"   -> best orientation: {min(eer_ours, eer_upstream):.4f}\n")

    if len(results) == 2:
        names = list(results)
        orig = min(results[names[0]].values())
        fine = min(results[names[1]].values())
        print("=" * 68)
        print(f"original weights, best orientation : EER {orig:.4f}")
        print(f"our fine-tune,    best orientation : EER {fine:.4f}")
        if fine < orig:
            print(f"\nFine-tuning HELPED: {orig - fine:.4f} absolute EER improvement.")
        else:
            print(f"\nFine-tuning HURT: the original weights are {fine - orig:.4f} "
                  f"absolute EER BETTER on this split.\n"
                  "Ship the original weights and treat the fine-tune as a regression.")
        print("=" * 68)


if __name__ == "__main__":
    main()
