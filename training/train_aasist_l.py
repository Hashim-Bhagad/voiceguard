"""Fine-tune official AASIST-L on an Indic anti-spoof manifest in Colab."""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
import torch
import yaml
from sklearn.metrics import roc_curve
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.dataset import SpoofDataset, assert_no_leakage, load_metadata
from src.model import build_model


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def eer(y_true: np.ndarray, scores: np.ndarray) -> float:
    if len(np.unique(y_true)) != 2:
        raise ValueError("EER requires both bonafide and spoof examples")
    fpr, tpr, _ = roc_curve(y_true, scores)
    fnr = 1.0 - tpr
    index = np.nanargmin(np.abs(fpr - fnr))
    return float((fpr[index] + fnr[index]) / 2.0)


@torch.inference_mode()
def score_loader(model: torch.nn.Module, loader: DataLoader, device: torch.device) -> tuple[np.ndarray, np.ndarray]:
    labels, scores = [], []
    model.eval()
    for waveform, label in loader:
        logits = model(waveform.to(device))
        scores.extend(torch.softmax(logits, dim=1)[:, 1].cpu().numpy())
        labels.extend(label.numpy())
    return np.asarray(labels), np.asarray(scores)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/aasist_l.yaml")
    parser.add_argument("--pretrained", default=None, help="Optional official AASIST-L .pth checkpoint")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    set_seed(int(cfg["seed"]))

    df = load_metadata(cfg["data"]["metadata_csv"])
    assert_no_leakage(df)
    print("split sizes:", df.groupby(["split", "label"]).size().to_dict())

    if not torch.cuda.is_available() and cfg["train"].get("require_cuda", True):
        raise RuntimeError("A Colab GPU runtime is required for AASIST-L fine-tuning.")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("device:", device)

    model = build_model(cfg).to(device)
    if args.pretrained:
        missing, unexpected = model.load_pretrained(args.pretrained)
        print(f"loaded pretrained checkpoint; missing={len(missing)} unexpected={len(unexpected)}")
        if missing or unexpected:
            raise RuntimeError("Checkpoint is not compatible with the pinned AASIST-L architecture")

    common = {
        "batch_size": int(cfg["data"]["batch_size"]),
        "num_workers": int(cfg["data"]["num_workers"]),
        "pin_memory": device.type == "cuda",
    }
    train_loader = DataLoader(
        SpoofDataset(df, cfg["data"]["train_split"], cfg["sample_rate"], cfg["model"]["window_samples"], True, cfg["augmentation"]),
        shuffle=True,
        **common,
    )
    dev_loader = DataLoader(
        SpoofDataset(df, cfg["data"]["dev_split"], cfg["sample_rate"], cfg["model"]["window_samples"]),
        shuffle=False,
        **common,
    )

    class_weights = torch.tensor(cfg["train"]["class_weights"], dtype=torch.float32, device=device)
    criterion = torch.nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=float(cfg["train"]["lr"]),
        betas=tuple(cfg["train"]["betas"]),
        weight_decay=float(cfg["train"]["weight_decay"]),
        amsgrad=bool(cfg["train"]["amsgrad"]),
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=int(cfg["train"]["epochs"]), eta_min=float(cfg["train"]["min_lr"])
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda" and bool(cfg["train"]["mixed_precision"]))

    output_dir = Path(cfg["train"]["out_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    best_eer, stagnant = float("inf"), 0
    for epoch in range(1, int(cfg["train"]["epochs"]) + 1):
        model.train()
        total_loss = 0.0
        for waveform, label in tqdm(train_loader, desc=f"epoch {epoch}"):
            waveform, label = waveform.to(device), label.to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=scaler.is_enabled()):
                logits = model(waveform, freq_aug=bool(cfg["augmentation"].get("frequency_mask", False)))
                loss = criterion(logits, label)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(cfg["train"]["grad_clip_norm"]))
            scaler.step(optimizer)
            scaler.update()
            total_loss += float(loss.item())
        scheduler.step()

        dev_y, dev_scores = score_loader(model, dev_loader, device)
        dev_eer = eer(dev_y, dev_scores)
        mean_loss = total_loss / max(1, len(train_loader))
        print(f"epoch={epoch} train_loss={mean_loss:.4f} dev_eer={dev_eer:.4f} lr={scheduler.get_last_lr()[0]:.2e}")
        if dev_eer < best_eer:
            best_eer, stagnant = dev_eer, 0
            torch.save(
                {"model": model.state_dict(), "config": cfg, "epoch": epoch, "dev_eer": dev_eer},
                output_dir / "best.pt",
            )
            print(f"saved {output_dir / 'best.pt'}")
        else:
            stagnant += 1
            if stagnant >= int(cfg["train"]["patience"]):
                print("early stopping")
                break
    print(f"best_dev_eer={best_eer:.4f}")


if __name__ == "__main__":
    main()
