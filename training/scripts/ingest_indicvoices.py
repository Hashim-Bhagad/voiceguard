"""Ingest bona-fide Indic speech from AI4Bharat IndicVoices.

IndicVoices is huge (11.2k transcribed hours across 22 languages), so this
streams a per-language cap instead of mirroring the repository.

Verified schema (dataset revision resolved at run time):
  * configs are **language names**: "hindi", "marathi", "tamil", ... There is
    NO english / en-IN config -- IndicVoices covers Indian languages only.
  * splits are "train" and "valid".
  * the audio column is ``audio_filepath`` (not ``audio``) and the language
    column is ``lang`` (not ``language``). Speaker is ``speaker_id``.

The repository is gated ("auto"): accept the terms on the dataset page once,
then put a read token in training/.env as HF_TOKEN.

Everything collected here is bona-fide. Nothing in this script may ever emit
label=spoof -- an Indian-language genuine corpus is not a deepfake corpus.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))

from src.ingest import ClipWriter, load_local_env  # noqa: E402

REPO_ID = "ai4bharat/IndicVoices"
AUDIO_FIELD = "audio_filepath"
LANGUAGE_FIELD = "lang"
SPEAKER_FIELD = "speaker_id"
DEFAULT_LANGUAGES = ("hindi", "marathi", "tamil", "bengali")


def decode_audio(value) -> tuple:
    """Return (mono float32 array, sample rate) from any shape `datasets` hands back.

    datasets < 4 yields {"array", "sampling_rate"}. datasets >= 4 decodes through
    torchcodec, which is often missing (Colab), so the column is cast to
    Audio(decode=False) and the raw {"bytes", "path"} is decoded here instead.
    A torchcodec AudioDecoder is handled too, in case decoding stayed on.
    """
    import io

    import numpy as np
    import soundfile as sf

    if hasattr(value, "get_all_samples"):  # torchcodec AudioDecoder
        samples = value.get_all_samples()
        return samples.data.mean(dim=0).numpy().astype(np.float32), int(samples.sample_rate)
    if not isinstance(value, dict):
        raise RuntimeError(f"{AUDIO_FIELD} has an unexpected type: {type(value)}")
    if "array" in value:
        return np.asarray(value["array"], dtype=np.float32), int(value["sampling_rate"])
    raw = value.get("bytes")
    if raw is None and value.get("path"):
        raw = Path(value["path"]).read_bytes()
    if raw is None:
        raise RuntimeError(f"{AUDIO_FIELD} has neither audio bytes nor a path: {list(value)}")
    try:
        wav, rate = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
    except Exception:  # noqa: BLE001 - fall back to librosa/audioread for odd containers
        import librosa

        wav, rate = librosa.load(io.BytesIO(raw), sr=None, mono=True)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    return wav.astype(np.float32), int(rate)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default=REPO_ID)
    parser.add_argument(
        "--languages",
        nargs="+",
        default=list(DEFAULT_LANGUAGES),
        help="IndicVoices config names (language names, e.g. hindi marathi tamil)",
    )
    parser.add_argument("--source-split", default="train", choices=("train", "valid"))
    parser.add_argument("--max-per-language", type=int, default=400)
    parser.add_argument("--min-duration", type=float, default=2.0)
    parser.add_argument("--max-duration", type=float, default=15.0)
    parser.add_argument(
        "--max-per-speaker",
        type=int,
        default=8,
        help="Cap clips per speaker so a few talkers cannot dominate a language",
    )
    parser.add_argument("--output-root", default=str(TRAINING_ROOT / "data"))
    parser.add_argument("--name", default="indicvoices")
    parser.add_argument(
        "--license-or-consent",
        default="CC-BY-4.0; IndicVoices gated terms accepted by the operator",
    )
    args = parser.parse_args()

    load_local_env()
    token = os.getenv("HF_TOKEN")
    if not token:
        raise SystemExit(
            "HF_TOKEN is not set. IndicVoices is a gated dataset: accept the terms at\n"
            f"  https://huggingface.co/datasets/{args.repo_id}\n"
            "then add HF_TOKEN=hf_... to training/.env (see .env.example)."
        )

    from datasets import Audio, load_dataset
    from huggingface_hub import HfApi

    revision = HfApi(token=token).dataset_info(args.repo_id).sha
    print(f"{args.repo_id} @ {revision}")

    writer = ClipWriter(
        source_dataset=args.name,
        license_or_consent=args.license_or_consent,
        output_root=Path(args.output_root),
        min_duration_s=args.min_duration,
        max_duration_s=args.max_duration,
    )
    per_language: dict[str, int] = {}

    for language in args.languages:
        print(f"\n[{language}] streaming {args.source_split} split, cap {args.max_per_language}")
        stream = load_dataset(
            args.repo_id,
            language,
            split=args.source_split,
            streaming=True,
            revision=revision,
            token=token,
        )
        features = getattr(stream, "features", None)
        if features and AUDIO_FIELD in features:
            stream = stream.cast_column(AUDIO_FIELD, Audio(decode=False))  # see decode_audio
        columns = set(getattr(stream, "column_names", None) or [])
        if columns and AUDIO_FIELD not in columns:
            raise RuntimeError(
                f"Expected an '{AUDIO_FIELD}' column in {args.repo_id}/{language}; found "
                f"{sorted(columns)}. The upstream schema changed -- update this script."
            )

        speaker_counts: Counter[str] = Counter()
        kept = 0
        for index, record in enumerate(stream):
            if kept >= args.max_per_language:
                break
            speaker = str(record.get(SPEAKER_FIELD) or f"unknown_{index}")
            if speaker_counts[speaker] >= args.max_per_speaker:
                continue
            wav, rate = decode_audio(record.get(AUDIO_FIELD))
            added = writer.add(
                wav,
                rate,
                stem=f"{language}_{kept:05d}",
                label="bonafide",
                speaker_id=speaker,
                language=record.get(LANGUAGE_FIELD) or language,
                subdir=f"bonafide/{language}",
            )
            if added:
                speaker_counts[speaker] += 1
                kept += 1
                if kept % 50 == 0:
                    print(f"  {kept}/{args.max_per_language}")

        per_language[language] = kept
        print(f"  kept {kept} clips from {len(speaker_counts)} speakers")
        if kept < args.max_per_language:
            print(
                f"  ! only {kept}/{args.max_per_language} for {language}; the stream ended or the "
                "per-speaker cap bound first."
            )

    print("\n" + writer.summary())
    writer.write_candidate(
        {
            "repo_id": args.repo_id,
            "revision": revision,
            "source_split": args.source_split,
            "languages": args.languages,
            "per_language_kept": per_language,
            "max_per_language": args.max_per_language,
            "max_per_speaker": args.max_per_speaker,
            "audio_field": AUDIO_FIELD,
            "language_field": LANGUAGE_FIELD,
            "speaker_field": SPEAKER_FIELD,
        },
        name=args.name,
    )


if __name__ == "__main__":
    main()
