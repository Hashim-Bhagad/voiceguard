"""Ingest the In-the-Wild audio deepfake dataset (Muller et al., 2022).

The dataset is 58 English-speaking celebrities/politicians scraped from online
video: 20.7 h bona-fide and 17.2 h spoofed, 37.9 h total. It is the
generalisation benchmark in this project -- real-world recording conditions
rather than a clean lab corpus.

Source options:
  1. Hugging Face mirror ``mueller91/In-The-Wild`` (public, ungated,
     CC-BY-SA-4.0) -- a single ``release_in_the_wild.zip``. This is the default
     because it needs no Kaggle credentials.
  2. Kaggle ``awsaf49/in-the-wild-audio-deepfake-dataset`` -- same content;
     download and unzip it yourself, then pass --local-dir.

Layout inside the archive is a flat directory plus a metadata CSV whose columns
are detected at run time (file / speaker / label, where label is "bona-fide" or
"spoof"). Column detection is explicit so an upstream rename fails loudly rather
than silently mislabelling clips.
"""
from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from collections import Counter
from pathlib import Path

TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))

from src.ingest import ClipWriter, load_local_env, retry  # noqa: E402

REPO_ID = "mueller91/In-The-Wild"
ZIP_NAME = "release_in_the_wild.zip"

FILE_KEYS = ("file", "filename", "path", "audio", "clip")
SPEAKER_KEYS = ("speaker", "speaker_id", "name", "celebrity")
LABEL_KEYS = ("label", "class", "target", "type")
BONAFIDE_VALUES = {"bona-fide", "bonafide", "bona fide", "real", "genuine", "0"}
SPOOF_VALUES = {"spoof", "fake", "deepfake", "synthetic", "1"}


def pick_column(header: list[str], candidates: tuple[str, ...], what: str) -> str:
    lowered = {name.strip().lower(): name for name in header}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    raise SystemExit(
        f"Could not find the {what} column in the metadata CSV.\n"
        f"  header:     {header}\n"
        f"  looked for: {list(candidates)}\n"
        "Pass the right name explicitly with the matching --*-column flag."
    )


def normalise_label(value: str) -> str:
    text = str(value).strip().lower()
    if text in BONAFIDE_VALUES:
        return "bonafide"
    if text in SPOOF_VALUES:
        return "spoof"
    raise SystemExit(
        f"Unrecognised label value {value!r}. Extend BONAFIDE_VALUES/SPOOF_VALUES "
        "rather than guessing -- a wrong mapping inverts the whole dataset."
    )


def find_metadata_csv(root: Path) -> Path:
    candidates = sorted(root.rglob("*.csv"))
    if not candidates:
        raise SystemExit(f"No CSV metadata found under {root}")
    for path in candidates:
        if path.name.lower() in {"meta.csv", "metadata.csv"}:
            return path
    print(f"  using {candidates[0].name} as the metadata CSV")
    return candidates[0]


def download_zip(local_dir: Path, repo_id: str) -> tuple[Path, str]:
    import os

    from huggingface_hub import HfApi, hf_hub_download

    token = os.getenv("HF_TOKEN")
    revision = retry(lambda: HfApi(token=token).dataset_info(repo_id).sha, what="dataset_info")
    print(f"{repo_id} @ {revision}\ndownloading {ZIP_NAME} (~7 GB) ...")
    path = retry(
        lambda: hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            filename=ZIP_NAME,
            revision=revision,
            local_dir=str(local_dir),
            token=token,
        ),
        what="hf_hub_download",
    )
    return Path(path), revision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default=REPO_ID)
    parser.add_argument(
        "--local-dir",
        default=str(TRAINING_ROOT / "data" / "sources" / "in-the-wild"),
        help="Download/extraction directory, or an existing unzipped copy",
    )
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--file-column", default=None)
    parser.add_argument("--speaker-column", default=None)
    parser.add_argument("--label-column", default=None)
    parser.add_argument("--min-duration", type=float, default=1.5)
    parser.add_argument("--max-duration", type=float, default=15.0)
    parser.add_argument(
        "--max-per-label",
        type=int,
        default=2500,
        help="Cap clips per label. The full set is ~31k clips; the default keeps "
             "CPU training tractable. Use 0 for everything.",
    )
    parser.add_argument(
        "--max-per-speaker",
        type=int,
        default=60,
        help="Cap clips per speaker per label so a few celebrities cannot dominate",
    )
    parser.add_argument("--output-root", default=str(TRAINING_ROOT / "data"))
    parser.add_argument("--name", default="in_the_wild")
    parser.add_argument("--license-or-consent", default="CC-BY-SA-4.0")
    args = parser.parse_args()

    load_local_env()
    local_dir = Path(args.local_dir).resolve()
    local_dir.mkdir(parents=True, exist_ok=True)
    revision = "local"

    if not args.skip_download and not any(local_dir.rglob("*.csv")):
        archive, revision = download_zip(local_dir, args.repo_id)
        print(f"extracting {archive.name} ...")
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(local_dir)

    metadata_csv = find_metadata_csv(local_dir)
    print(f"metadata: {metadata_csv}")
    with metadata_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        file_col = args.file_column or pick_column(header, FILE_KEYS, "file")
        speaker_col = args.speaker_column or pick_column(header, SPEAKER_KEYS, "speaker")
        label_col = args.label_column or pick_column(header, LABEL_KEYS, "label")
        print(f"columns: file={file_col!r} speaker={speaker_col!r} label={label_col!r}")
        records = list(reader)
    print(f"{len(records)} rows in metadata")

    audio_root = metadata_csv.parent
    writer = ClipWriter(
        source_dataset=args.name,
        license_or_consent=args.license_or_consent,
        output_root=Path(args.output_root),
        min_duration_s=args.min_duration,
        max_duration_s=args.max_duration,
    )

    label_counts: Counter[str] = Counter()
    speaker_label_counts: Counter[tuple[str, str]] = Counter()
    missing_files = 0

    for record in records:
        label = normalise_label(record[label_col])
        if args.max_per_label and label_counts[label] >= args.max_per_label:
            continue
        speaker = str(record[speaker_col]).strip() or "unknown"
        if speaker_label_counts[(speaker, label)] >= args.max_per_speaker:
            continue

        relative = str(record[file_col]).strip()
        path = audio_root / relative
        if not path.is_file():
            matches = list(audio_root.rglob(Path(relative).name))
            if not matches:
                missing_files += 1
                continue
            path = matches[0]

        # In-the-Wild does not publish which system produced each spoof clip, so
        # the generator is recorded as an explicit unknown rather than invented.
        if writer.add_file(
            path,
            stem=f"{Path(relative).stem}",
            label=label,
            speaker_id=speaker,
            language="en",
            attack_family="none" if label == "bonafide" else "in_the_wild",
            generator="none" if label == "bonafide" else "in_the_wild_unknown",
            codec="web",
            noise_condition="in_the_wild",
            subdir=label,
        ):
            label_counts[label] += 1
            speaker_label_counts[(speaker, label)] += 1

    if missing_files:
        print(f"  ! {missing_files} rows referenced audio that could not be located")
    speakers = {speaker for speaker, _ in speaker_label_counts}
    print(f"\n{len(speakers)} distinct speakers, per-label counts {dict(label_counts)}")
    print(writer.summary())
    writer.write_candidate(
        {
            "repo_id": args.repo_id if not args.skip_download else None,
            "revision": revision,
            "local_dir": str(local_dir),
            "metadata_csv": str(metadata_csv),
            "columns": {"file": file_col, "speaker": speaker_col, "label": label_col},
            "max_per_label": args.max_per_label,
            "max_per_speaker": args.max_per_speaker,
            "speakers": len(speakers),
            "missing_files": missing_files,
            "citation": "Muller et al., Does Audio Deepfake Detection Generalize? arXiv:2203.16263",
        },
        name=args.name,
    )


if __name__ == "__main__":
    main()
