"""Validated manifest loader and waveform augmentation for AASIST-L."""
from __future__ import annotations

import random
from pathlib import Path

import librosa
import numpy as np
import pandas as pd
import soundfile as sf
import torch
from torch.utils.data import Dataset

REQUIRED_COLS = {
    "clip_path", "label", "attack_family", "generator", "language", "speaker_id", "split"
}
VALID_LABELS = {"bonafide": 0, "spoof": 1}
NO_GENERATOR_VALUES = {"", "none", "nan", "null", "-"}


def load_metadata(csv_path: str | Path) -> pd.DataFrame:
    csv_path = Path(csv_path).resolve()
    df = pd.read_csv(csv_path)
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        raise ValueError(f"metadata.csv missing required columns: {sorted(missing)}")
    df = df.copy()
    df["label"] = df["label"].astype(str).str.lower().str.strip()
    unknown = set(df["label"]) - set(VALID_LABELS)
    if unknown:
        raise ValueError(f"label must be bonafide or spoof, found: {sorted(unknown)}")
    df["split"] = df["split"].astype(str).str.lower().str.strip()
    if set(df["split"]) - {"train", "dev", "test"}:
        raise ValueError("split must be train, dev, or test")
    df["clip_path"] = df["clip_path"].map(
        lambda path: str((csv_path.parent / path).resolve()) if not Path(path).is_absolute() else str(Path(path))
    )
    return df


def _spoof_generators(rows: pd.DataFrame) -> set[str]:
    values = rows.loc[rows.label == "spoof", "generator"].fillna("").astype(str).str.strip().str.lower()
    return {value for value in values if value not in NO_GENERATOR_VALUES}


def assert_no_leakage(df: pd.DataFrame) -> None:
    for split in ("train", "dev", "test"):
        rows = df[df.split == split]
        if rows.empty:
            raise ValueError(f"{split} split is empty")
        labels = set(rows.label)
        if labels != set(VALID_LABELS):
            raise ValueError(f"{split} split must contain bonafide and spoof examples")

    for left, right in (("train", "dev"), ("train", "test"), ("dev", "test")):
        overlap = set(df[df.split == left].speaker_id) & set(df[df.split == right].speaker_id)
        if overlap:
            raise ValueError(f"speaker leakage {left}/{right}: {sorted(overlap)[:5]}")

    train_generators = _spoof_generators(df[df.split == "train"])
    for split in ("dev", "test"):
        held_out = _spoof_generators(df[df.split == split]) - train_generators
        if not held_out:
            raise ValueError(
                f"{split} has no held-out spoof generator. Keep a full TTS/VC generator unseen during training."
            )


def _read_audio(path: str, sample_rate: int) -> np.ndarray:
    wav, source_rate = sf.read(path, dtype="float32", always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    if source_rate != sample_rate:
        wav = librosa.resample(wav, orig_sr=source_rate, target_sr=sample_rate)
    return np.asarray(wav, dtype=np.float32)


def _take_window(wav: np.ndarray, samples: int, train: bool) -> np.ndarray:
    if len(wav) >= samples:
        start = random.randint(0, len(wav) - samples) if train else (len(wav) - samples) // 2
        return wav[start:start + samples].copy()
    return np.pad(wav, (0, samples - len(wav))).astype(np.float32)


def _random_file(directory: str | None) -> Path | None:
    if not directory:
        return None
    files = [*Path(directory).glob("**/*.wav"), *Path(directory).glob("**/*.flac")]
    return random.choice(files) if files else None


def _mix_noise(wav: np.ndarray, sample_rate: int, noise_dir: str | None) -> np.ndarray:
    path = _random_file(noise_dir)
    if path is None:
        return wav
    noise = _take_window(_read_audio(str(path), sample_rate), len(wav), train=True)
    snr_db = random.uniform(5.0, 20.0)
    signal_rms = np.sqrt(np.mean(wav ** 2) + 1e-9)
    noise_rms = np.sqrt(np.mean(noise ** 2) + 1e-9)
    return wav + noise * (signal_rms / noise_rms) * (10.0 ** (-snr_db / 20.0))


def _apply_rir(wav: np.ndarray, sample_rate: int, rir_dir: str | None) -> np.ndarray:
    path = _random_file(rir_dir)
    if path is None:
        return wav
    rir = _read_audio(str(path), sample_rate)
    if not len(rir):
        return wav
    rir = rir / (np.sqrt(np.sum(rir ** 2)) + 1e-9)
    return np.convolve(wav, rir, mode="full")[:len(wav)]


def _narrowband_roundtrip(wav: np.ndarray, sample_rate: int) -> np.ndarray:
    narrow = librosa.resample(wav, orig_sr=sample_rate, target_sr=8000)
    return librosa.resample(narrow, orig_sr=8000, target_sr=sample_rate)


class SpoofDataset(Dataset):
    def __init__(
        self,
        df: pd.DataFrame,
        split: str,
        sample_rate: int = 16000,
        window_samples: int = 64600,
        train: bool = False,
        augmentation: dict | None = None,
    ):
        self.rows = df[df.split == split].reset_index(drop=True)
        self.sample_rate = sample_rate
        self.window_samples = window_samples
        self.train = train
        self.augmentation = augmentation or {}

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        row = self.rows.iloc[index]
        wav = _take_window(_read_audio(row.clip_path, self.sample_rate), self.window_samples, self.train)
        if self.train:
            if random.random() < float(self.augmentation.get("narrowband_prob", 0.0)):
                wav = _narrowband_roundtrip(wav, self.sample_rate)
            if random.random() < float(self.augmentation.get("noise_prob", 0.0)):
                wav = _mix_noise(wav, self.sample_rate, self.augmentation.get("noise_dir"))
            if random.random() < float(self.augmentation.get("rir_prob", 0.0)):
                wav = _apply_rir(wav, self.sample_rate, self.augmentation.get("rir_dir"))
            gain = 10.0 ** (random.uniform(-3.0, 3.0) / 20.0)
            wav = np.clip(wav * gain, -1.0, 1.0)
        return torch.from_numpy(wav.astype(np.float32)), torch.tensor(VALID_LABELS[row.label], dtype=torch.long)
