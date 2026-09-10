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

    from datasets import load_dataset
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
            audio = record.get(AUDIO_FIELD)
            if not isinstance(audio, dict) or "array" not in audio:
                raise RuntimeError(
                    f"{AUDIO_FIELD} is not a decoded datasets Audio value (got {type(audio)})."
                )
            speaker = str(record.get(SPEAKER_FIELD) or f"unknown_{index}")
            if speaker_counts[speaker] >= args.max_per_speaker:
                continue
            added = writer.add(
                audio["array"],
                int(audio["sampling_rate"]),
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
