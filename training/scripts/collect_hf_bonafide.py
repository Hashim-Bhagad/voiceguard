"""Stream a capped, provenance-recorded bona-fide subset from Hugging Face."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter
from pathlib import Path

import soundfile as sf
from datasets import load_dataset
from huggingface_hub import HfApi


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def field(row: dict, name: str) -> object:
    if name not in row:
        raise KeyError(f"Missing field '{name}'. Inspect the dataset schema first.")
    return row[name]


def clean_name(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--config", default=None)
    parser.add_argument("--source-split", default="train")
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--target-split", choices=("train", "dev", "test"), required=True)
    parser.add_argument("--languages", nargs="+", required=True)
    parser.add_argument("--max-per-language", type=int, required=True)
    parser.add_argument("--audio-field", default="audio")
    parser.add_argument("--language-field", default="language")
    parser.add_argument("--speaker-field", default="speaker_id")
    parser.add_argument("--license-or-consent", required=True)
    parser.add_argument("--output-root", default="data")
    args = parser.parse_args()

    load_local_env()
    token = os.getenv("HF_TOKEN")
    resolved_revision = HfApi(token=token).dataset_info(args.repo_id).sha
    stream = load_dataset(
        args.repo_id,
        args.config,
        split=args.source_split,
        streaming=True,
        revision=resolved_revision,
        token=token,
    )
    output_root = Path(args.output_root).resolve()
    source_dir = output_root / "audio" / args.target_split / "bonafide" / clean_name(args.source_name)
    candidate_dir = output_root / "candidates"
    source_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    wanted = {language.lower(): language for language in args.languages}
    counts: Counter[str] = Counter()
    rows: list[dict[str, str]] = []
    for index, record in enumerate(stream):
        language = str(field(record, args.language_field)).strip().lower()
        if language not in wanted or counts[language] >= args.max_per_language:
            continue
        audio = field(record, args.audio_field)
        if not isinstance(audio, dict) or "array" not in audio or "sampling_rate" not in audio:
            raise ValueError("Expected datasets Audio object with array and sampling_rate fields")
        speaker = f"{args.source_name}:{field(record, args.speaker_field)}"
        destination = source_dir / f"{clean_name(language)}_{counts[language]:04d}.wav"
        sf.write(destination, audio["array"], int(audio["sampling_rate"]))
        rows.append({
            "clip_path": str(destination.relative_to(output_root)),
            "label": "bonafide",
            "attack_family": "none",
            "generator": "none",
            "language": wanted[language],
            "speaker_id": speaker,
            "split": args.target_split,
            "codec": "source",
            "noise_condition": "source",
            "source_dataset": args.source_name,
            "license_or_consent": args.license_or_consent,
        })
        counts[language] += 1
        if all(counts[key] >= args.max_per_language for key in wanted):
            break
    if any(counts[key] < args.max_per_language for key in wanted):
        raise RuntimeError(f"Source exhausted before requested counts: {dict(counts)}")
    candidate_path = candidate_dir / f"{clean_name(args.source_name)}_{args.target_split}_bonafide.csv"
    with candidate_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (candidate_path.with_suffix(".source.json")).write_text(
        json.dumps({"repo_id": args.repo_id, "revision": resolved_revision, "source_split": args.source_split}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} clips to {candidate_path}; per-language={dict(counts)}")


if __name__ == "__main__":
    main()
