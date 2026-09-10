"""Generate vocoder-resynthesis spoof clips from bona-fide audio.

WHY THIS EXISTS
---------------
With IndicVoices + garystafford + In-the-Wild, every Indic clip is bona-fide and
every spoof clip is English. A classifier can then reach a near-zero training EER
by learning "sounds Indic => genuine" instead of learning synthesis artifacts,
and it will miss real Hindi/Tamil/Marathi clones in production. Balancing English
on both sides helps, but it does not put any Indic audio on the spoof side.

This script closes that gap without a GPU and without a TTS licence: it takes
bona-fide clips and re-synthesises them through a vocoder-style analysis and
resynthesis pass. Essentially every TTS and voice-conversion system ends with a
vocoder, and the phase/harmonic damage that stage leaves behind is a large part
of what raw-waveform detectors like AASIST actually key on.

WHAT THIS IS NOT
----------------
These are **not** voice clones. The linguistic content and speaker identity are
unchanged; only the signal path is synthetic. So:

  * They teach the model to be sensitive to vocoder artifacts in Indic audio.
  * They do NOT prove the model detects, say, IndicF5 or XTTS clones.
  * They are labelled ``attack_family=vocoded`` with a per-method ``generator``
    so you can report on them separately, hold them out, or drop them entirely.

Do not report a headline "Indic deepfake detection EER" that rests on these
clips. Treat them as an auxiliary training family and a floor, not a benchmark.
Once you can generate real consented Indic TTS/VC clips, add them as their own
generators and re-run.

Methods (all CPU-only, all pure numpy/scipy):
  griffinlim   magnitude STFT -> iterative phase reconstruction (phase discarded)
  melgriffin   mel filterbank -> pseudo-inverse -> Griffin-Lim (adds mel smearing)
  phasereset   STFT with phase replaced by noise, then inverse (harsh, obvious)
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import signal as sps

TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))

from src.ingest import ClipWriter, TARGET_SAMPLE_RATE  # noqa: E402

N_FFT = 512
HOP = 128
METHODS = ("griffinlim", "melgriffin", "phasereset")


def _stft(wav: np.ndarray) -> np.ndarray:
    _, _, spectrum = sps.stft(
        wav, nperseg=N_FFT, noverlap=N_FFT - HOP, window="hann", boundary=None, padded=True
    )
    return spectrum


def _istft(spectrum: np.ndarray, length: int) -> np.ndarray:
    _, wav = sps.istft(
        spectrum, nperseg=N_FFT, noverlap=N_FFT - HOP, window="hann", boundary=None
    )
    wav = np.asarray(wav, dtype=np.float32)
    if len(wav) < length:
        wav = np.pad(wav, (0, length - len(wav)))
    return wav[:length]


def _griffin_lim(magnitude: np.ndarray, length: int, iterations: int, rng: np.random.Generator) -> np.ndarray:
    """Reconstruct a signal from magnitudes only; original phase is thrown away."""
    angle = np.exp(2j * np.pi * rng.random(magnitude.shape))
    spectrum = magnitude * angle
    wav = _istft(spectrum, length)
    for _ in range(iterations):
        rebuilt = _stft(wav)
        # Keep the target magnitude, keep only the phase we just estimated.
        phase = np.exp(1j * np.angle(rebuilt))
        frames = min(magnitude.shape[1], phase.shape[1])
        wav = _istft(magnitude[:, :frames] * phase[:, :frames], length)
    return wav


def _mel_filterbank(n_mels: int, sample_rate: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    def to_mel(hz: np.ndarray | float) -> np.ndarray | float:
        return 2595.0 * np.log10(1.0 + np.asarray(hz) / 700.0)

    def to_hz(mel: np.ndarray) -> np.ndarray:
        return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)

    n_bins = N_FFT // 2 + 1
    fft_freqs = np.linspace(0.0, sample_rate / 2.0, n_bins)
    mel_points = np.linspace(to_mel(0.0), to_mel(sample_rate / 2.0), n_mels + 2)
    hz_points = to_hz(mel_points)
    bank = np.zeros((n_mels, n_bins), dtype=np.float32)
    for m in range(n_mels):
        left, centre, right = hz_points[m], hz_points[m + 1], hz_points[m + 2]
        rising = (fft_freqs - left) / max(centre - left, 1e-9)
        falling = (right - fft_freqs) / max(right - centre, 1e-9)
        bank[m] = np.clip(np.minimum(rising, falling), 0.0, None)
    return bank


def vocode(wav: np.ndarray, method: str, rng: np.random.Generator) -> np.ndarray:
    length = len(wav)
    spectrum = _stft(wav)
    magnitude = np.abs(spectrum)

    if method == "griffinlim":
        out = _griffin_lim(magnitude, length, iterations=int(rng.integers(24, 40)), rng=rng)
    elif method == "melgriffin":
        n_mels = int(rng.choice([64, 80]))
        bank = _mel_filterbank(n_mels)
        mel = bank @ magnitude
        # Pseudo-inverse back to linear frequency: this is the lossy step real
        # mel-vocoder pipelines also have to undo.
        approx = np.maximum(np.linalg.pinv(bank) @ mel, 0.0)
        out = _griffin_lim(approx, length, iterations=int(rng.integers(20, 32)), rng=rng)
    elif method == "phasereset":
        angle = np.exp(2j * np.pi * rng.random(magnitude.shape))
        out = _istft(magnitude * angle, length)
    else:
        raise ValueError(f"unknown method {method!r}")

    peak = float(np.max(np.abs(out)))
    if peak > 0:
        out = out / peak * float(np.max(np.abs(wav)) or 0.9)
    return np.asarray(out, dtype=np.float32)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--from-candidate",
        default="data/candidates/indicvoices.csv",
        help="Candidate CSV of bona-fide source clips to re-synthesise",
    )
    parser.add_argument("--data-root", default=str(TRAINING_ROOT / "data"))
    parser.add_argument("--methods", nargs="+", default=list(METHODS), choices=list(METHODS))
    parser.add_argument("--max-per-language", type=int, default=200)
    parser.add_argument(
        "--exclude-speaker-fraction",
        type=float,
        default=0.5,
        help="Reserve this fraction of source speakers for spoof generation only. "
             "Using the same speaker as bona-fide AND spoof lets the model shortcut "
             "on speaker identity, so the sets are kept disjoint.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-duration", type=float, default=2.0)
    parser.add_argument("--max-duration", type=float, default=15.0)
    parser.add_argument("--name", default="vocoded_indic")
    parser.add_argument("--output-root", default=str(TRAINING_ROOT / "data"))
    args = parser.parse_args()

    import pandas as pd
    import soundfile as sf

    data_root = Path(args.data_root).resolve()
    candidate = Path(args.from_candidate)
    if not candidate.is_absolute():
        candidate = (TRAINING_ROOT / candidate).resolve()
    if not candidate.is_file():
        raise SystemExit(
            f"{candidate} not found. Run the bona-fide ingest first, e.g.\n"
            "  python scripts/ingest_indicvoices.py"
        )

    df = pd.read_csv(candidate)
    df = df[df.label == "bonafide"].copy()
    if df.empty:
        raise SystemExit(f"{candidate} has no bona-fide rows to re-synthesise.")

    rng = np.random.default_rng(args.seed)

    # Split source speakers: only the reserved half becomes spoof material.
    speakers = sorted(df.speaker_id.unique())
    rng.shuffle(speakers)
    reserved_count = max(1, int(len(speakers) * args.exclude_speaker_fraction))
    reserved = set(speakers[:reserved_count])
    print(f"{len(speakers)} source speakers; {len(reserved)} reserved for spoof generation")
    usable = df[df.speaker_id.isin(reserved)]
    if usable.empty:
        raise SystemExit("No clips left after reserving speakers; lower --exclude-speaker-fraction.")

    writer = ClipWriter(
        source_dataset=args.name,
        license_or_consent=(
            f"Derived by vocoder resynthesis from {candidate.stem}; "
            "inherits the source dataset licence. Not a voice clone."
        ),
        output_root=Path(args.output_root),
        min_duration_s=args.min_duration,
        max_duration_s=args.max_duration,
    )

    per_language: Counter[str] = Counter()
    produced: Counter[str] = Counter()
    for language, group in usable.groupby("language"):
        group = group.sample(frac=1.0, random_state=args.seed).reset_index(drop=True)
        print(f"\n[{language}] {len(group)} candidate source clips")
        for _, row in group.iterrows():
            if per_language[language] >= args.max_per_language:
                break
            source = data_root / str(row.clip_path)
            if not source.is_file():
                continue
            try:
                wav, rate = sf.read(str(source), dtype="float32", always_2d=False)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! unreadable {source}: {exc}")
                continue
            if wav.ndim > 1:
                wav = wav.mean(axis=1)
            method = str(rng.choice(args.methods))
            try:
                synthetic = vocode(np.asarray(wav, dtype=np.float32), method, rng)
            except Exception as exc:  # noqa: BLE001
                print(f"  ! vocoding failed for {source.name} ({method}): {exc}")
                continue

            generator = f"vocoder_{method}"
            if writer.add(
                synthetic,
                int(rate),
                stem=f"{language}_{method}_{per_language[language]:05d}",
                label="spoof",
                # Namespace the speaker so this clip can never collide with the
                # bona-fide row it was derived from.
                speaker_id=f"voc_{row.speaker_id}",
                language=language,
                attack_family="vocoded",
                generator=generator,
                codec="resynth",
                subdir=f"spoof/{method}/{language}",
            ):
                per_language[language] += 1
                produced[generator] += 1
                if per_language[language] % 25 == 0:
                    print(f"  {per_language[language]}/{args.max_per_language}")
        print(f"  produced {per_language[language]} clips for {language}")

    print("\n" + writer.summary())
    writer.write_candidate(
        {
            "derived_from": str(candidate),
            "source_speakers_total": len(speakers),
            "source_speakers_reserved_for_spoof": sorted(reserved),
            "methods": args.methods,
            "per_generator": dict(produced),
            "seed": args.seed,
            "caveat": (
                "Vocoder resynthesis, not voice cloning. Linguistic content and speaker "
                "identity are unchanged. Use as an auxiliary training family only; do not "
                "report it as Indic voice-clone detection performance."
            ),
        },
        name=args.name,
    )
    print(
        "\nReminder: these clips make the model artifact-sensitive in Indic languages.\n"
        "They are not evidence that it detects a real Indic TTS/VC clone."
    )


if __name__ == "__main__":
    main()
