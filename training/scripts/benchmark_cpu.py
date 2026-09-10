"""Measure AASIST-L throughput on this machine and project training time.

Answers two questions that decide whether a local run is practical:

  1. Is training compute-bound or data-bound? (thread scaling vs dataloader rate)
  2. How long does one epoch take for a given number of training clips?

Run it before committing to a long run:

    .venv/bin/python scripts/benchmark_cpu.py
    .venv/bin/python scripts/benchmark_cpu.py --train-clips 12000 --epochs 20
"""
from __future__ import annotations

import argparse
import platform
import sys
import time
from pathlib import Path

import torch
import yaml

TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))

from src.model import build_model  # noqa: E402


def human_time(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 5400:
        return f"{seconds / 60:.1f} min"
    if seconds < 172800:
        return f"{seconds / 3600:.1f} h"
    return f"{seconds / 86400:.1f} days"


def time_steps(model, batch: int, samples: int, steps: int, train: bool) -> float:
    """Return clips/second over `steps` measured steps (after 2 warmup steps)."""
    waveform = torch.randn(batch, samples)
    label = torch.randint(0, 2, (batch,))
    criterion = torch.nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

    def one_step() -> None:
        if train:
            model.train()
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(waveform), label)
            loss.backward()
            optimizer.step()
        else:
            model.eval()
            with torch.inference_mode():
                model(waveform)

    for _ in range(2):
        one_step()
    start = time.perf_counter()
    for _ in range(steps):
        one_step()
    elapsed = time.perf_counter() - start
    return (batch * steps) / elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(TRAINING_ROOT / "configs" / "aasist_l.yaml"))
    parser.add_argument("--batch-size", type=int, default=None, help="Defaults to config value")
    parser.add_argument("--steps", type=int, default=6)
    parser.add_argument(
        "--threads", type=int, nargs="*", default=None,
        help="Thread counts to sweep (default: 1, half, all cores)",
    )
    parser.add_argument(
        "--train-clips", type=int, nargs="*", default=[1108, 4000, 8000, 16000, 32000],
        help="Training-set sizes to project epoch time for",
    )
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--dev-clips", type=int, default=0, help="Dev clips scored each epoch")
    parser.add_argument("--skip-dataloader", action="store_true")
    args = parser.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    samples = int(cfg["model"]["window_samples"])
    batch = int(args.batch_size or cfg["data"]["batch_size"])
    cores = torch.get_num_threads()
    import os
    logical = os.cpu_count() or cores

    print(f"machine   : {platform.machine()} | {logical} logical cores")
    print(f"torch     : {torch.__version__} | cuda_available={torch.cuda.is_available()}")
    print(f"model     : AASIST-L, window {samples} samples ({samples / 16000:.2f} s), batch {batch}")

    if torch.cuda.is_available():
        print("\nNOTE: a CUDA device is visible. These CPU numbers are a floor, not what you will get.")

    model = build_model(cfg)
    print(f"parameters: {model.num_parameters():,}\n")

    thread_list = args.threads or sorted({1, max(1, logical // 2), logical})
    print(f"{'threads':>8}  {'train clips/s':>14}  {'infer clips/s':>14}  {'s/step (train)':>15}")
    results: dict[int, float] = {}
    infer_results: dict[int, float] = {}
    for threads in thread_list:
        torch.set_num_threads(threads)
        train_rate = time_steps(model, batch, samples, args.steps, train=True)
        infer_rate = time_steps(model, batch, samples, args.steps, train=False)
        results[threads] = train_rate
        infer_results[threads] = infer_rate
        print(f"{threads:>8}  {train_rate:>14.2f}  {infer_rate:>14.2f}  {batch / train_rate:>15.2f}")

    best_threads = max(results, key=lambda k: results[k])
    best_rate = results[best_threads]
    print(f"\nbest training throughput: {best_rate:.2f} clips/s at {best_threads} threads")
    if len(results) > 1:
        baseline = results[min(results)]
        print(f"scaling from {min(results)} thread: {best_rate / baseline:.2f}x")

    # --- is the dataloader keeping up? -------------------------------------
    loader_rate = None
    if not args.skip_dataloader:
        metadata = TRAINING_ROOT / cfg["data"]["metadata_csv"]
        if metadata.is_file():
            from torch.utils.data import DataLoader

            from src.dataset import SpoofDataset, load_metadata, seed_worker

            df = load_metadata(metadata)
            workers = int(cfg["data"].get("num_workers", 0))
            dataset = SpoofDataset(
                df, cfg["data"]["train_split"], cfg["sample_rate"], samples,
                train=True, augmentation=cfg["augmentation"],
                cache_dir=(cfg.get("runtime") or {}).get("cache_dir"), seed=0,
            )
            loader = DataLoader(
                dataset, batch_size=batch, shuffle=True, num_workers=workers,
                worker_init_fn=seed_worker if workers else None,
            )
            iterator = iter(loader)
            next(iterator)  # warm up workers
            measured = 0
            start = time.perf_counter()
            for _ in range(min(args.steps, len(loader) - 1)):
                waveform, _ = next(iterator)
                measured += int(waveform.shape[0])
            loader_rate = measured / (time.perf_counter() - start)
            print(
                f"\ndataloader alone ({workers} workers, augmentation on): "
                f"{loader_rate:.1f} clips/s"
            )
            if loader_rate < best_rate * 1.2:
                print("  -> DATA-BOUND: raise data.num_workers or warm runtime.cache_dir")
            else:
                print("  -> COMPUTE-BOUND: the model, not audio decoding, sets the pace")
        else:
            print(f"\ndataloader benchmark skipped: {metadata} not found")

    # --- project epoch and run time ---------------------------------------
    effective = best_rate if loader_rate is None else min(best_rate, loader_rate)
    print(f"\nprojection at {effective:.2f} clips/s ({best_threads} threads)")
    print(f"{'train clips':>12}  {'1 epoch':>10}  {f'{args.epochs} epochs':>12}")
    for clips in args.train_clips:
        epoch_seconds = clips / effective
        if args.dev_clips:
            epoch_seconds += args.dev_clips / infer_results[best_threads]
        print(
            f"{clips:>12}  {human_time(epoch_seconds):>10}  "
            f"{human_time(epoch_seconds * args.epochs):>12}"
        )

    print(
        "\nNotes:"
        "\n  * Add dev-split scoring per epoch with --dev-clips N (uses the inference rate)."
        "\n  * Early stopping usually ends a fine-tune well before the epoch cap, so treat the"
        "\n    right-hand column as a worst case."
        "\n  * train.max_hours + --resume let you split a long run across sittings."
    )


if __name__ == "__main__":
    main()
