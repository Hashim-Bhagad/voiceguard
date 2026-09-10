"""Measure AASIST-L memory and throughput on this machine, safely.

Why this script is careful about memory
---------------------------------------
AASIST-L has only 85,306 parameters, but it is an activation-heavy model. The
sinc-conv front end produces a (batch, 70, 64472) map, and the first encoder
block expands that to (batch, 32, 23, 21490) -- about 1 GB at batch 16 for a
single tensor, before autograd saves the intermediates it needs for backward.
Naively benchmarking at batch 16 on a 15 GB laptop OOM-killed the process at
5.1 GB resident and took the desktop with it.

So this script:
  * caps its own address space with RLIMIT_AS, so it dies cleanly instead of
    driving the machine into the OOM killer;
  * starts at batch 1 and grows, reporting peak RSS at each step;
  * stops as soon as a batch size exceeds the memory budget.

Usage:
    .venv/bin/python scripts/benchmark_cpu.py                  # probe + throughput
    .venv/bin/python scripts/benchmark_cpu.py --budget-gb 3    # tighter cap
"""
from __future__ import annotations

import argparse
import gc
import os
import platform
import resource
import sys
import time
from pathlib import Path

TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))


def peak_rss_gb() -> float:
    """Peak resident set size of this process, in GiB (Linux reports KiB)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 ** 2)


def current_rss_gb() -> float:
    try:
        with open("/proc/self/statm", encoding="utf-8") as handle:
            pages = int(handle.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / (1024 ** 3)
    except (OSError, IndexError, ValueError):
        return float("nan")


def available_gb() -> float:
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024 ** 2)
    except OSError:
        pass
    return float("nan")


def apply_address_space_cap(limit_gb: float) -> None:
    """Hard-cap this process so a bad probe cannot take the desktop down."""
    limit_bytes = int(limit_gb * (1024 ** 3))
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    ceiling = limit_bytes if hard == resource.RLIM_INFINITY else min(limit_bytes, hard)
    resource.setrlimit(resource.RLIMIT_AS, (ceiling, hard))
    print(f"address-space cap: {ceiling / (1024 ** 3):.1f} GiB (RLIMIT_AS)")


def human_time(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 5400:
        return f"{seconds / 60:.1f} min"
    if seconds < 172800:
        return f"{seconds / 3600:.1f} h"
    return f"{seconds / 86400:.1f} days"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default=str(TRAINING_ROOT / "configs" / "aasist_l.yaml"))
    parser.add_argument(
        "--budget-gb", type=float, default=2.5,
        help="Per-process memory budget for a training step. Batch sizes needing "
             "more than this are reported as unsafe.",
    )
    parser.add_argument(
        "--cap-gb", type=float, default=None,
        help="RLIMIT_AS ceiling (default: budget + 2 GiB headroom)",
    )
    parser.add_argument("--batches", type=int, nargs="*", default=[1, 2, 4, 6, 8, 12, 16])
    parser.add_argument("--threads", type=int, nargs="*", default=None)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--train-clips", type=int, nargs="*",
                        default=[1108, 4000, 8000, 16000, 30000])
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--dev-clips", type=int, default=0)
    args = parser.parse_args()

    apply_address_space_cap(args.cap_gb if args.cap_gb else args.budget_gb + 2.0)

    import torch
    import yaml

    from src.model import build_model

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    samples = int(cfg["model"]["window_samples"])
    logical = os.cpu_count() or 1

    print(f"machine  : {platform.machine()}, {logical} logical cores")
    print(f"torch    : {torch.__version__}, cuda_available={torch.cuda.is_available()}")
    print(f"memory   : {available_gb():.1f} GiB available now")
    print(f"model    : AASIST-L, {samples} samples ({samples / 16000:.2f} s) per clip")
    print(f"budget   : {args.budget_gb:.1f} GiB per training step\n")

    model = build_model(cfg)
    print(f"parameters: {model.num_parameters():,}")
    baseline = current_rss_gb()
    print(f"model resident: {baseline:.2f} GiB\n")

    criterion = torch.nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

    def train_step(waveform: torch.Tensor, label: torch.Tensor) -> None:
        model.train()
        optimizer.zero_grad(set_to_none=True)
        criterion(model(waveform), label).backward()
        optimizer.step()

    def infer_step(waveform: torch.Tensor) -> None:
        model.eval()
        with torch.inference_mode():
            model(waveform)

    # ---- memory probe: grow the batch until it stops being affordable ------
    print("=== memory probe (batch size vs peak RSS, one training step) ===")
    print(f"{'batch':>6}  {'peak RSS':>10}  {'delta':>9}  verdict")
    safe_batches: list[int] = []
    for batch in sorted(args.batches):
        gc.collect()
        before = peak_rss_gb()
        try:
            waveform = torch.randn(batch, samples)
            label = torch.randint(0, 2, (batch,))
            train_step(waveform, label)
            del waveform, label
            gc.collect()
        except (MemoryError, RuntimeError) as exc:
            print(f"{batch:>6}  {'--':>10}  {'--':>9}  FAILED ({type(exc).__name__})")
            break
        peak = peak_rss_gb()
        delta = peak - before
        ok = peak <= args.budget_gb
        if ok:
            safe_batches.append(batch)
        print(
            f"{batch:>6}  {peak:>9.2f}G  {delta:>8.2f}G  "
            f"{'ok' if ok else 'OVER BUDGET'}"
        )
        if not ok:
            break

    if not safe_batches:
        raise SystemExit(
            f"Even batch {min(args.batches)} exceeded {args.budget_gb} GiB. "
            "Raise --budget-gb or train on a machine with more RAM."
        )
    best_batch = max(safe_batches)
    print(f"\nlargest batch within budget: {best_batch}")

    # ---- thread scaling at the safe batch ---------------------------------
    thread_list = sorted({t for t in (args.threads or [1, max(1, logical // 2), logical])
                          if 1 <= t <= logical})
    print(f"\n=== throughput at batch {best_batch} ===")
    print(f"{'threads':>8}  {'train clip/s':>13}  {'s/step':>8}  {'infer clip/s':>13}")
    waveform = torch.randn(best_batch, samples)
    label = torch.randint(0, 2, (best_batch,))
    train_rates: dict[int, float] = {}
    infer_rates: dict[int, float] = {}
    for threads in thread_list:
        torch.set_num_threads(threads)
        for _ in range(2):
            train_step(waveform, label)
        start = time.perf_counter()
        for _ in range(args.steps):
            train_step(waveform, label)
        train_rate = (best_batch * args.steps) / (time.perf_counter() - start)

        infer_step(waveform)
        start = time.perf_counter()
        for _ in range(args.steps):
            infer_step(waveform)
        infer_rate = (best_batch * args.steps) / (time.perf_counter() - start)

        train_rates[threads] = train_rate
        infer_rates[threads] = infer_rate
        print(
            f"{threads:>8}  {train_rate:>13.2f}  {best_batch / train_rate:>8.2f}  "
            f"{infer_rate:>13.2f}"
        )

    best_threads = max(train_rates, key=lambda k: train_rates[k])
    best_rate = train_rates[best_threads]
    print(f"\nbest: {best_rate:.2f} clips/s at {best_threads} threads, batch {best_batch}")
    if len(train_rates) > 1:
        slowest = train_rates[min(train_rates)]
        print(f"scaling from 1 thread: {best_rate / slowest:.2f}x")
    print(f"peak RSS overall: {peak_rss_gb():.2f} GiB")

    # ---- projection -------------------------------------------------------
    print(f"\n=== projected wall clock at {best_rate:.2f} clips/s ===")
    print(f"{'train clips':>12}  {'1 epoch':>10}  {f'{args.epochs} epochs':>12}")
    for clips in args.train_clips:
        epoch_seconds = clips / best_rate
        if args.dev_clips:
            epoch_seconds += args.dev_clips / infer_rates[best_threads]
        print(
            f"{clips:>12}  {human_time(epoch_seconds):>10}  "
            f"{human_time(epoch_seconds * args.epochs):>12}"
        )

    print(
        f"\nSuggested config for this machine:\n"
        f"  data.batch_size: {best_batch}\n"
        f"  train.grad_accum_steps: {max(1, 16 // best_batch)}   "
        f"(keeps an effective batch near 16)\n"
        f"  runtime.num_threads: {best_threads}\n"
        "\nKeep data.num_workers low: each worker is a separate process holding its own\n"
        "decoded audio, and they compete with the model for both RAM and cores."
    )


if __name__ == "__main__":
    main()
