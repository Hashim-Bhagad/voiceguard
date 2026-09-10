"""Manifest loading, waveform windowing, and label-neutral augmentation for AASIST-L.

Design rules that matter for anti-spoofing correctness:

* Short clips are **repeat-padded**, matching the official AASIST ``pad()``. Zero
  padding would leave a silent tail whose length correlates with clip duration,
  and clip duration correlates with the source dataset, which correlates with
  the label. That is a shortcut the model will happily learn instead of learning
  synthesis artifacts.
* Every stochastic transform is applied **independently of the label**. If noise
  or codec augmentation were applied to only one class, the augmentation itself
  becomes the discriminative feature.
* If a configured augmentation corpus is missing we fall back to a synthetic
  generator and say so, rather than silently disabling the augmentation.
"""
from __future__ import annotations

import hashlib
import os
import random
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf
import soxr
import torch
from torch.utils.data import Dataset

REQUIRED_COLS = {
    "clip_path", "label", "attack_family", "generator", "language", "speaker_id", "split",
}
VALID_LABELS = {"bonafide": 0, "spoof": 1}
VALID_SPLITS = {"train", "dev", "test"}
NO_GENERATOR_VALUES = {"", "none", "nan", "null", "-", "na"}

# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def load_metadata(csv_path: str | Path) -> pd.DataFrame:
    """Load and normalise data/metadata.csv, resolving clip paths against it."""
    csv_path = Path(csv_path).resolve()
    if not csv_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {csv_path}")
    df = pd.read_csv(csv_path)
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"metadata.csv missing required columns: {sorted(missing)}")

    df = df.copy()
    df["label"] = df["label"].astype(str).str.lower().str.strip()
    unknown_labels = set(df["label"]) - set(VALID_LABELS)
    if unknown_labels:
        raise ValueError(f"label must be bonafide or spoof, found: {sorted(unknown_labels)}")

    df["split"] = df["split"].astype(str).str.lower().str.strip()
    unknown_splits = set(df["split"]) - VALID_SPLITS
    if unknown_splits:
        raise ValueError(f"split must be train, dev, or test, found: {sorted(unknown_splits)}")

    for column in ("attack_family", "generator", "language", "speaker_id"):
        df[column] = df[column].fillna("none").astype(str).str.strip()

    df["clip_path"] = df["clip_path"].map(
        lambda path: str(Path(path)) if Path(path).is_absolute()
        else str((csv_path.parent / path).resolve())
    )

    duplicated = df["clip_path"].duplicated()
    if duplicated.any():
        first = df.loc[duplicated, "clip_path"].iloc[0]
        raise ValueError(
            f"{int(duplicated.sum())} duplicate clip_path rows in the manifest; first: {first}. "
            "Duplicates across splits leak evaluation data into training."
        )
    return df


def spoof_generators(rows: pd.DataFrame) -> set[str]:
    values = rows.loc[rows.label == "spoof", "generator"].astype(str).str.strip().str.lower()
    return {value for value in values if value not in NO_GENERATOR_VALUES}


def assert_no_leakage(df: pd.DataFrame, require_unseen_generator: bool = True) -> None:
    """Fail loudly on the split mistakes that silently inflate anti-spoofing scores."""
    for split in ("train", "dev", "test"):
        rows = df[df.split == split]
        if rows.empty:
            raise ValueError(f"{split} split is empty")
        labels = set(rows.label)
        if labels != set(VALID_LABELS):
            raise ValueError(
                f"{split} split must contain both bonafide and spoof examples, found {sorted(labels)}"
            )

    for left, right in (("train", "dev"), ("train", "test"), ("dev", "test")):
        overlap = set(df[df.split == left].speaker_id) & set(df[df.split == right].speaker_id)
        if overlap:
            raise ValueError(
                f"speaker leakage {left}/{right} ({len(overlap)} shared): {sorted(overlap)[:5]}"
            )

    if not require_unseen_generator:
        return
    train_generators = spoof_generators(df[df.split == "train"])
    for split in ("dev", "test"):
        held_out = spoof_generators(df[df.split == split]) - train_generators
        if not held_out:
            raise ValueError(
                f"{split} has no spoof generator that is unseen in train. Hold out at least one "
                "full TTS/VC family, otherwise the reported EER only measures in-generator recall."
            )


# ---------------------------------------------------------------------------
# Audio IO
# ---------------------------------------------------------------------------


def read_audio(path: str | Path, sample_rate: int) -> np.ndarray:
    """Decode to mono float32 at ``sample_rate``. Uses soxr (VHQ) for resampling."""
    wav, source_rate = sf.read(str(path), dtype="float32", always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    wav = np.ascontiguousarray(wav, dtype=np.float32)
    if wav.size == 0:
        raise ValueError(f"Decoded zero samples from {path}")
    if source_rate != sample_rate:
        wav = soxr.resample(wav, source_rate, sample_rate, quality="VHQ")
    return np.ascontiguousarray(wav, dtype=np.float32)


def stable_seed(*parts: object) -> int:
    """Hash to a 32-bit seed that does not depend on PYTHONHASHSEED."""
    raw = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.blake2b(raw, digest_size=4).digest(), "big")


def _cache_key(path: str, sample_rate: int) -> str:
    stat = os.stat(path)
    raw = f"{path}|{stat.st_size}|{int(stat.st_mtime)}|{sample_rate}".encode()
    return hashlib.sha1(raw).hexdigest()


def read_audio_cached(path: str, sample_rate: int, cache_dir: Path | None) -> np.ndarray:
    """Decode with an optional on-disk float32 cache.

    On a CPU-only box, FLAC decode plus resampling is a meaningful fraction of
    step time. Caching the decoded 16 kHz mono signal (not the crop, so random
    cropping still varies per epoch) removes that cost from epochs 2..N.
    """
    if cache_dir is None:
        return read_audio(path, sample_rate)
    key = _cache_key(path, sample_rate)
    cached = cache_dir / key[:2] / f"{key}.npy"
    if cached.is_file():
        try:
            return np.load(cached, mmap_mode=None).astype(np.float32, copy=False)
        except (ValueError, OSError):
            cached.unlink(missing_ok=True)  # truncated cache entry; re-decode
    wav = read_audio(path, sample_rate)
    cached.parent.mkdir(parents=True, exist_ok=True)
    # Write via a handle: np.save(path) would append a second ".npy" suffix.
    # Unique temp name per process so concurrent DataLoader workers cannot clash.
    temporary = cached.with_name(f"{cached.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as handle:
            np.save(handle, wav, allow_pickle=False)
        os.replace(temporary, cached)
    finally:
        temporary.unlink(missing_ok=True)
    return wav


def repeat_pad(wav: np.ndarray, samples: int) -> np.ndarray:
    """Tile the signal up to ``samples``, as the official AASIST pad() does."""
    if len(wav) >= samples:
        return wav[:samples]
    repeats = int(np.ceil(samples / len(wav)))
    return np.tile(wav, repeats)[:samples].astype(np.float32, copy=False)


def take_window(wav: np.ndarray, samples: int, train: bool, rng: random.Random) -> np.ndarray:
    """Random crop for training, deterministic centre crop for dev/test."""
    if len(wav) < samples:
        wav = repeat_pad(wav, samples)
    if len(wav) == samples:
        return np.ascontiguousarray(wav, dtype=np.float32)
    start = rng.randint(0, len(wav) - samples) if train else (len(wav) - samples) // 2
    return np.ascontiguousarray(wav[start:start + samples], dtype=np.float32)


# ---------------------------------------------------------------------------
# Augmentation (identical treatment for both labels)
# ---------------------------------------------------------------------------


def _coloured_noise(length: int, rng: np.random.Generator) -> np.ndarray:
    """White / pink / brown noise, used when no real noise corpus is available."""
    white = rng.standard_normal(length).astype(np.float32)
    exponent = float(rng.choice([0.0, 1.0, 2.0]))
    if exponent == 0.0:
        return white
    spectrum = np.fft.rfft(white)
    frequencies = np.fft.rfftfreq(length, d=1.0)
    scale = np.ones_like(frequencies)
    nonzero = frequencies > 0
    scale[nonzero] = 1.0 / (frequencies[nonzero] ** (exponent / 2.0))
    shaped = np.fft.irfft(spectrum * scale, n=length).astype(np.float32)
    peak = float(np.max(np.abs(shaped))) or 1.0
    return shaped / peak


def _synthetic_rir(sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    """Exponentially decaying noise burst: a crude but real small-room RIR."""
    rt60 = float(rng.uniform(0.15, 0.6))
    length = max(16, int(rt60 * sample_rate))
    decay = np.exp(-6.907 * np.arange(length) / (rt60 * sample_rate))
    impulse = rng.standard_normal(length).astype(np.float32) * decay.astype(np.float32)
    impulse[0] += 1.0  # keep a strong direct path
    return impulse


def _mix_noise(wav: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    signal_rms = float(np.sqrt(np.mean(wav ** 2) + 1e-12))
    noise_rms = float(np.sqrt(np.mean(noise ** 2) + 1e-12))
    gain = (signal_rms / noise_rms) * (10.0 ** (-snr_db / 20.0))
    return (wav + noise * gain).astype(np.float32)


def _apply_rir(wav: np.ndarray, impulse: np.ndarray) -> np.ndarray:
    energy = float(np.sqrt(np.sum(impulse ** 2)) + 1e-12)
    convolved = np.convolve(wav, impulse / energy, mode="full")[: len(wav)]
    return convolved.astype(np.float32)


def _narrowband_roundtrip(wav: np.ndarray, sample_rate: int, rng: np.random.Generator) -> np.ndarray:
    """Simulate a telephony leg: resample down to 8 kHz and back up."""
    intermediate = int(rng.choice([8000, 8000, 11025]))
    narrow = soxr.resample(wav, sample_rate, intermediate, quality="HQ")
    restored = soxr.resample(narrow, intermediate, sample_rate, quality="HQ")
    return repeat_pad(np.ascontiguousarray(restored, dtype=np.float32), len(wav))


class Augmenter:
    """Label-neutral waveform augmentation with explicit fallbacks."""

    AUDIO_SUFFIXES = (".wav", ".flac", ".ogg", ".mp3")

    def __init__(self, config: dict | None, sample_rate: int):
        config = config or {}
        self.sample_rate = sample_rate
        self.narrowband_prob = float(config.get("narrowband_prob", 0.0))
        self.noise_prob = float(config.get("noise_prob", 0.0))
        self.rir_prob = float(config.get("rir_prob", 0.0))
        self.gain_db = float(config.get("gain_db", 3.0))
        self.snr_db_range = tuple(config.get("snr_db_range", (5.0, 20.0)))
        self.frequency_mask = bool(config.get("frequency_mask", False))
        self.noise_files = self._index(config.get("noise_dir"), "noise_dir", self.noise_prob)
        self.rir_files = self._index(config.get("rir_dir"), "rir_dir", self.rir_prob)

    def _index(self, directory: str | None, name: str, probability: float) -> list[Path]:
        if not directory or probability <= 0.0:
            return []
        root = Path(directory)
        if not root.is_dir():
            warnings.warn(
                f"augmentation.{name}={directory!r} does not exist; falling back to a synthetic "
                f"generator for this augmentation (probability {probability}).",
                stacklevel=2,
            )
            return []
        files = [p for p in root.rglob("*") if p.suffix.lower() in self.AUDIO_SUFFIXES]
        if not files:
            warnings.warn(
                f"augmentation.{name}={directory!r} contains no audio files; using the synthetic "
                "fallback instead.",
                stacklevel=2,
            )
        return files

    def describe(self) -> str:
        noise = f"{len(self.noise_files)} files" if self.noise_files else "synthetic"
        rir = f"{len(self.rir_files)} files" if self.rir_files else "synthetic"
        return (
            f"narrowband_p={self.narrowband_prob} noise_p={self.noise_prob} ({noise}) "
            f"rir_p={self.rir_prob} ({rir}) gain=+/-{self.gain_db}dB"
        )

    def __call__(self, wav: np.ndarray, rng: random.Random, nprng: np.random.Generator) -> np.ndarray:
        if self.narrowband_prob and rng.random() < self.narrowband_prob:
            wav = _narrowband_roundtrip(wav, self.sample_rate, nprng)

        if self.noise_prob and rng.random() < self.noise_prob:
            if self.noise_files:
                path = self.noise_files[rng.randrange(len(self.noise_files))]
                noise = take_window(
                    read_audio(path, self.sample_rate), len(wav), train=True, rng=rng
                )
            else:
                noise = _coloured_noise(len(wav), nprng)
            wav = _mix_noise(wav, noise, float(nprng.uniform(*self.snr_db_range)))

        if self.rir_prob and rng.random() < self.rir_prob:
            if self.rir_files:
                path = self.rir_files[rng.randrange(len(self.rir_files))]
                impulse = read_audio(path, self.sample_rate)
            else:
                impulse = _synthetic_rir(self.sample_rate, nprng)
            if impulse.size:
                wav = _apply_rir(wav, impulse)

        if self.gain_db:
            gain = 10.0 ** (float(nprng.uniform(-self.gain_db, self.gain_db)) / 20.0)
            wav = wav * gain

        peak = float(np.max(np.abs(wav)))
        if peak > 1.0:  # rescale rather than hard-clip, which adds its own artifacts
            wav = wav / peak
        return np.ascontiguousarray(wav, dtype=np.float32)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------


class SpoofDataset(Dataset):
    """Serves fixed-length 16 kHz windows and binary labels for one split."""

    def __init__(
        self,
        df: pd.DataFrame,
        split: str,
        sample_rate: int = 16000,
        window_samples: int = 64600,
        train: bool = False,
        augmentation: dict | None = None,
        cache_dir: str | Path | None = None,
        seed: int = 0,
    ):
        self.rows = df[df.split == split].reset_index(drop=True)
        if self.rows.empty:
            raise ValueError(f"No rows for split={split!r}")
        self.split = split
        self.sample_rate = int(sample_rate)
        self.window_samples = int(window_samples)
        self.train = bool(train)
        self.seed = int(seed)
        self.augmenter = Augmenter(augmentation, self.sample_rate) if train else None
        self.cache_dir = Path(cache_dir).resolve() if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.targets = self.rows.label.map(VALID_LABELS).to_numpy()

    def __len__(self) -> int:
        return len(self.rows)

    def _rngs(self, index: int) -> tuple[random.Random, np.random.Generator]:
        if self.train:
            # Draw from the per-worker, per-epoch state that ``seed_worker`` seeds
            # from ``torch.initial_seed()``. This keeps crops and augmentation
            # varying every epoch while staying reproducible for a given run seed.
            return random, np.random.default_rng(np.random.randint(0, 2 ** 32))
        # Dev/test must score identically across runs, workers and machines.
        stream = stable_seed(self.seed, self.split, index)
        return random.Random(stream), np.random.default_rng(stream)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        row = self.rows.iloc[index]
        rng, nprng = self._rngs(index)

        wav = read_audio_cached(row.clip_path, self.sample_rate, self.cache_dir)
        wav = take_window(wav, self.window_samples, self.train, rng)
        if self.augmenter is not None:
            wav = self.augmenter(wav, rng, nprng)
            wav = take_window(wav, self.window_samples, train=False, rng=rng)

        return (
            torch.from_numpy(np.ascontiguousarray(wav, dtype=np.float32)),
            torch.tensor(int(VALID_LABELS[row.label]), dtype=torch.long),
        )


def seed_worker(worker_id: int) -> None:
    """DataLoader worker_init_fn: give each worker a distinct, run-reproducible stream."""
    seed = torch.initial_seed() % (2 ** 32)
    np.random.seed(seed)
    random.seed(seed)


def balanced_sample_weights(
    df: pd.DataFrame, split: str, by: tuple[str, ...] = ("label", "language")
) -> np.ndarray:
    """Inverse-frequency weights over (label x language) for WeightedRandomSampler.

    Without this, a large English spoof corpus plus a small Indic bona-fide
    corpus produces batches where "English" and "spoof" are correlated, which is
    exactly the confound we are trying to avoid.
    """
    rows = df[df.split == split].reset_index(drop=True)
    if rows.empty:
        raise ValueError(f"No rows for split={split!r}")
    columns = [column for column in by if column in rows.columns]
    if not columns:
        return np.ones(len(rows), dtype=np.float64)
    groups = rows[columns].astype(str).agg("|".join, axis=1)
    counts = groups.value_counts()
    return (1.0 / groups.map(counts)).to_numpy(dtype=np.float64)
