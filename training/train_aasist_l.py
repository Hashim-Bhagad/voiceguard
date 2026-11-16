"""Fine-tune official AASIST-L on a multilingual anti-spoof manifest, locally.

Runs on CPU or CUDA with no code change (runtime.device=auto). Designed for a
laptop: it checkpoints every epoch, can resume, and can stop on a wall-clock
budget so a long run can be split across sittings.

  python train_aasist_l.py --config configs/aasist_l.yaml \
      --pretrained weights/AASIST-L.pth

  python train_aasist_l.py --resume          # continue from outputs/.../last.pt
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import random
import time
from pathlib import Path

import numpy as np
import torch
import yaml
from sklearn.metrics import roc_curve
from torch.utils.data import DataLoader, WeightedRandomSampler
from tqdm import tqdm

from src.dataset import (
    SpoofDataset, assert_no_leakage, balanced_sample_weights, load_metadata, seed_worker,
)
from src.model import build_model, model_type


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def resolve_device(requested: str) -> torch.device:
    requested = str(requested or "auto").lower()
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise SystemExit(
                "runtime.device=cuda but no CUDA device is visible. Use 'auto' or 'cpu'."
            )
        return torch.device("cuda")
    if requested == "cpu":
        return torch.device("cpu")
    if requested != "auto":
        raise SystemExit(f"runtime.device must be auto, cpu or cuda; got {requested!r}")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def resolve_amp_dtype(requested: str, enabled: bool) -> torch.dtype:
    """bf16 on GPUs that support it (A100, L4, H100), fp16 otherwise (T4, V100)."""
    requested = str(requested or "auto").lower()
    if not enabled:
        return torch.float32
    if requested == "auto":
        return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    if requested in ("bf16", "bfloat16"):
        return torch.bfloat16
    if requested in ("fp16", "float16"):
        return torch.float16
    raise SystemExit(f"train.amp_dtype must be auto, bf16 or fp16; got {requested!r}")


def eer(y_true: np.ndarray, scores: np.ndarray) -> float:
    if len(np.unique(y_true)) != 2:
        raise ValueError("EER requires both bonafide and spoof examples")
    fpr, tpr, _ = roc_curve(y_true, scores)
    fnr = 1.0 - tpr
    index = int(np.nanargmin(np.abs(fpr - fnr)))
    return float((fpr[index] + fnr[index]) / 2.0)


@torch.inference_mode()
def score_loader(
    model: torch.nn.Module, loader: DataLoader, device: torch.device, desc: str = "eval"
) -> tuple[np.ndarray, np.ndarray]:
    labels: list[float] = []
    scores: list[float] = []
    model.eval()
    for waveform, label in tqdm(loader, desc=desc, leave=False):
        logits = model(waveform.to(device))
        scores.extend(torch.softmax(logits.float(), dim=1)[:, 1].cpu().numpy().tolist())
        labels.extend(label.numpy().tolist())
    return np.asarray(labels), np.asarray(scores)


def build_loaders(cfg: dict, df, device: torch.device, seed: int):
    data_cfg = cfg["data"]
    runtime_cfg = cfg.get("runtime", {}) or {}
    cache_dir = runtime_cfg.get("cache_dir")
    batch_size = int(data_cfg["batch_size"])
    num_workers = int(data_cfg["num_workers"])

    common = {
        "batch_size": batch_size,
        "num_workers": num_workers,
        "pin_memory": device.type == "cuda",
        "worker_init_fn": seed_worker if num_workers > 0 else None,
        "persistent_workers": num_workers > 0,
    }

    train_dataset = SpoofDataset(
        df, data_cfg["train_split"], cfg["sample_rate"], cfg["model"]["window_samples"],
        train=True, augmentation=cfg["augmentation"], cache_dir=cache_dir, seed=seed,
    )
    if train_dataset.augmenter is not None:
        print(f"augmentation: {train_dataset.augmenter.describe()}")

    if bool(data_cfg.get("balanced_sampler", False)):
        weights = balanced_sample_weights(
            df, data_cfg["train_split"], tuple(data_cfg.get("balance_by", ("label", "language")))
        )
        generator = torch.Generator().manual_seed(seed)
        sampler = WeightedRandomSampler(
            weights=torch.as_tensor(weights, dtype=torch.double),
            num_samples=len(train_dataset),
            replacement=True,
            generator=generator,
        )
        print(f"balanced sampler over {tuple(data_cfg.get('balance_by', ('label', 'language')))}")
        train_loader = DataLoader(train_dataset, sampler=sampler, drop_last=True, **common)
    else:
        train_loader = DataLoader(train_dataset, shuffle=True, drop_last=True, **common)

    dev_loader = DataLoader(
        SpoofDataset(
            df, data_cfg["dev_split"], cfg["sample_rate"], cfg["model"]["window_samples"],
            cache_dir=cache_dir, seed=seed,
        ),
        shuffle=False, **common,
    )
    return train_loader, dev_loader


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/aasist_l.yaml")
    parser.add_argument("--pretrained", default=None, help="Official AASIST-L .pth to initialise from")
    parser.add_argument("--resume", action="store_true", help="Continue from <out_dir>/last.pt")
    parser.add_argument("--device", default=None, help="Override runtime.device")
    parser.add_argument("--epochs", type=int, default=None, help="Override train.epochs")
    parser.add_argument("--max-hours", type=float, default=None, help="Override train.max_hours")
    parser.add_argument(
        "--allow-loose-checkpoint", action="store_true",
        help="Permit missing/unexpected keys when loading --pretrained",
    )
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    if args.epochs is not None:
        cfg["train"]["epochs"] = args.epochs
    if args.max_hours is not None:
        cfg["train"]["max_hours"] = args.max_hours

    seed = int(cfg["seed"])
    set_seed(seed)

    runtime_cfg = cfg.get("runtime", {}) or {}
    device = resolve_device(args.device or runtime_cfg.get("device", "auto"))
    threads = int(runtime_cfg.get("num_threads", 0) or 0)
    if threads > 0:
        torch.set_num_threads(threads)
    print(
        f"device={device} threads={torch.get_num_threads()} "
        f"torch={torch.__version__} python={platform.python_version()}"
    )

    df = load_metadata(cfg["data"]["metadata_csv"])
    assert_no_leakage(df)
    print("split/label counts:", df.groupby(["split", "label"]).size().to_dict())

    model = build_model(cfg).to(device)
    kind = model_type(cfg)
    if hasattr(model, "describe"):
        print(model.describe())
    else:
        print(f"AASIST-L parameters: {model.num_parameters():,} (all trainable)")

    output_dir = Path(cfg["train"]["out_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    last_path = output_dir / "last.pt"
    best_path = output_dir / "best.pt"
    history_path = output_dir / "history.csv"

    if args.pretrained and kind != "aasist_l":
        raise SystemExit(
            f"--pretrained loads an AASIST-L checkpoint; model.type={kind} initialises "
            "its encoder from model.ssl.pretrained instead. Drop --pretrained."
        )
    if args.pretrained and not args.resume:
        missing, unexpected = model.load_pretrained(args.pretrained)
        print(f"loaded {args.pretrained}: missing={len(missing)} unexpected={len(unexpected)}")
        if (missing or unexpected) and not args.allow_loose_checkpoint:
            raise SystemExit(
                "Checkpoint is not compatible with the pinned AASIST-L architecture. "
                "Pass --allow-loose-checkpoint only if you understand why keys differ."
            )

    criterion = torch.nn.CrossEntropyLoss(
        weight=torch.tensor(cfg["train"]["class_weights"], dtype=torch.float32, device=device)
    )
    # Frozen parameters are left out of the optimiser entirely: Adam's weight
    # decay would otherwise still nudge them, and their state would waste memory.
    param_groups = (
        model.optimizer_groups(cfg["train"]) if hasattr(model, "optimizer_groups")
        else [p for p in model.parameters() if p.requires_grad]
    )
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.Adam(
        param_groups,
        lr=float(cfg["train"]["lr"]),
        betas=tuple(cfg["train"]["betas"]),
        weight_decay=float(cfg["train"]["weight_decay"]),
        amsgrad=bool(cfg["train"]["amsgrad"]),
    )
    total_epochs = int(cfg["train"]["epochs"])
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=total_epochs, eta_min=float(cfg["train"]["min_lr"])
    )
    amp_enabled = device.type == "cuda" and bool(cfg["train"]["mixed_precision"])
    amp_dtype = resolve_amp_dtype(cfg["train"].get("amp_dtype", "auto"), amp_enabled)
    # bf16 has fp32's exponent range, so it needs no loss scaling; fp16 does.
    scaler = torch.amp.GradScaler(device.type, enabled=amp_enabled and amp_dtype == torch.float16)
    if amp_enabled:
        print(f"mixed precision: {str(amp_dtype).removeprefix('torch.')}")
    if device.type == "cpu" and bool(cfg["train"]["mixed_precision"]):
        print("note: mixed_precision ignored on CPU (fp32 is faster without AVX512-BF16)")

    start_epoch = 1
    best_eer = float("inf")
    stagnant = 0
    if args.resume:
        if not last_path.is_file():
            raise SystemExit(f"--resume given but {last_path} does not exist")
        blob = torch.load(last_path, map_location=device, weights_only=False)
        model.load_state_dict(blob["model"])
        optimizer.load_state_dict(blob["optimizer"])
        scheduler.load_state_dict(blob["scheduler"])
        if blob.get("scaler") and scaler.is_enabled():
            scaler.load_state_dict(blob["scaler"])
        start_epoch = int(blob["epoch"]) + 1
        best_eer = float(blob.get("best_eer", float("inf")))
        stagnant = int(blob.get("stagnant", 0))
        print(f"resumed from {last_path} at epoch {start_epoch} (best_dev_eer={best_eer:.4f})")

    train_loader, dev_loader = build_loaders(cfg, df, device, seed)
    accum = max(1, int(cfg["train"].get("grad_accum_steps", 1)))
    log_every = max(1, int(cfg["train"].get("log_every", 25)))
    max_hours = float(cfg["train"].get("max_hours", 0) or 0)
    freq_aug = bool(cfg["augmentation"].get("frequency_mask", False))
    started = time.time()

    if not history_path.exists():
        with history_path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(
                ["epoch", "train_loss", "dev_eer", "lr", "seconds", "clips_per_s"]
            )

    (output_dir / "config.used.yaml").write_text(
        yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8"
    )

    print(
        f"\ntraining: {len(train_loader)} steps/epoch x batch {cfg['data']['batch_size']} "
        f"(accum {accum}) for epochs {start_epoch}..{total_epochs}"
    )
    stop_reason = "completed all epochs"
    epoch = start_epoch - 1  # defined even when a finished run is resumed and the loop is empty
    patience = int(cfg["train"]["patience"])
    if start_epoch > total_epochs or stagnant >= patience:
        # Resuming a run that finished or early-stopped must not train further.
        stop_reason = "already complete; nothing to resume"
        print(f"{last_path} is from epoch {start_epoch - 1} of {total_epochs}: {stop_reason}")
        total_epochs = start_epoch - 1
    for epoch in range(start_epoch, total_epochs + 1):
        model.train()
        epoch_start = time.time()
        running = 0.0
        seen = 0
        optimizer.zero_grad(set_to_none=True)

        progress = tqdm(train_loader, desc=f"epoch {epoch}/{total_epochs}")
        for step, (waveform, label) in enumerate(progress, start=1):
            waveform = waveform.to(device, non_blocking=True)
            label = label.to(device, non_blocking=True)
            with torch.autocast(device_type=device.type, dtype=amp_dtype, enabled=amp_enabled):
                logits = model(waveform, freq_aug=freq_aug)
                loss = criterion(logits, label)
            scaler.scale(loss / accum).backward()

            if step % accum == 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(
                    trainable, float(cfg["train"]["grad_clip_norm"])
                )
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)

            running += float(loss.item()) * label.size(0)
            seen += int(label.size(0))
            if step % log_every == 0:
                elapsed = time.time() - epoch_start
                progress.set_postfix(
                    loss=f"{running / max(1, seen):.4f}", clips_s=f"{seen / max(elapsed, 1e-6):.1f}"
                )

        scheduler.step()
        epoch_seconds = time.time() - epoch_start
        mean_loss = running / max(1, seen)
        throughput = seen / max(epoch_seconds, 1e-6)

        dev_y, dev_scores = score_loader(model, dev_loader, device, desc=f"dev {epoch}")
        dev_eer = eer(dev_y, dev_scores)
        current_lr = scheduler.get_last_lr()[0]
        print(
            f"epoch={epoch} train_loss={mean_loss:.4f} dev_eer={dev_eer:.4f} "
            f"lr={current_lr:.2e} {epoch_seconds / 60:.1f} min ({throughput:.1f} clips/s)"
        )
        with history_path.open("a", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(
                [epoch, f"{mean_loss:.6f}", f"{dev_eer:.6f}", f"{current_lr:.3e}",
                 f"{epoch_seconds:.1f}", f"{throughput:.2f}"]
            )

        improved = dev_eer < best_eer
        if improved:
            best_eer, stagnant = dev_eer, 0
        else:
            stagnant += 1

        checkpoint = {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(),
            "scaler": scaler.state_dict() if scaler.is_enabled() else None,
            "config": cfg,
            "epoch": epoch,
            "dev_eer": dev_eer,
            "best_eer": best_eer,
            "stagnant": stagnant,
        }
        torch.save(checkpoint, last_path)
        if improved:
            torch.save(checkpoint, best_path)
            print(f"  new best dev EER; saved {best_path}")

        if stagnant >= int(cfg["train"]["patience"]):
            stop_reason = f"early stopping after {stagnant} epochs without improvement"
            print(stop_reason)
            break
        if max_hours and (time.time() - started) / 3600.0 >= max_hours:
            stop_reason = f"hit the {max_hours} h budget; rerun with --resume to continue"
            print(stop_reason)
            break

    summary = {
        "best_dev_eer": best_eer,
        "last_epoch": epoch,
        "total_epochs": total_epochs,
        "stop_reason": stop_reason,
        "device": str(device),
        "wall_clock_hours": round((time.time() - started) / 3600.0, 3),
        "best_checkpoint": str(best_path) if best_path.exists() else None,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"\nbest_dev_eer={best_eer:.4f}  ({stop_reason})")
    print(f"wrote {output_dir / 'summary.json'} and {history_path}")
    print(
        "\nNext: evaluate on the held-out test split, which contains spoof generators unseen\n"
        "during training. The dev EER above is a model-selection number, not a result.\n"
        f"  python eval.py --ckpt {best_path}"
    )


if __name__ == "__main__":
    main()
