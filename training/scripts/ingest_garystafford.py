"""Ingest garystafford/deepfake-audio-detection (English real + 6 TTS families).

This source is downloaded as **raw FLAC files** rather than through the parquet
export, because the filenames carry the two labels the parquet drops:

  * generator, from the prefix -- ``po_``=Amazon Polly, ``el_``=ElevenLabs,
    ``hg_``=Hexgrad Kokoro, ``hu_``=Hume AI, ``lv_``=Luvvoice, ``sp_``=Speechify.
  * speaker, from the ``yt_NNNN`` id of the source recording for real clips.

Without those we could not hold a generator family out of training, nor keep
speakers disjoint across splits -- both of which the manifest builder requires.

License: CC-BY-4.0. 1,866 clips (933 real / 933 fake), 16 kHz mono, 2.5-13 s.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))

from src.ingest import ClipWriter, download_snapshot, load_local_env  # noqa: E402

REPO_ID = "garystafford/deepfake-audio-detection"

# Prefix -> generator name, from the dataset card.
GENERATORS = {
    "po": "amazon_polly",
    "el": "elevenlabs",
    "hg": "hexgrad_kokoro",
    "hu": "hume_ai",
    "lv": "luvvoice",
    "sp": "speechify",
}

# fake/el_0009_c_part_004.flac -> ("el", "0009");  real/yt_0006_p2_part_007.flac -> ("yt", "0006")
STEM_RE = re.compile(r"^(?P<prefix>[a-z]{2})_(?P<id>\d+)")


def parse_stem(stem: str) -> tuple[str, str]:
    match = STEM_RE.match(stem)
    if not match:
        raise ValueError(f"Unrecognised filename stem {stem!r}; upstream naming changed.")
    return match.group("prefix"), match.group("id")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default=REPO_ID)
    parser.add_argument(
        "--local-dir",
        default=str(TRAINING_ROOT / "data" / "sources" / "garystafford-deepfake-audio-detection"),
        help="Where the raw real/ and fake/ FLAC files are downloaded to",
    )
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--min-duration", type=float, default=1.5)
    parser.add_argument("--max-duration", type=float, default=15.0)
    parser.add_argument(
        "--max-per-generator",
        type=int,
        default=0,
        help="0 means take everything; otherwise cap clips per TTS family",
    )
    parser.add_argument("--max-real", type=int, default=0, help="0 means take every real clip")
    parser.add_argument("--output-root", default=str(TRAINING_ROOT / "data"))
    parser.add_argument("--name", default="garystafford")
    parser.add_argument("--license-or-consent", default="CC-BY-4.0")
    args = parser.parse_args()

    load_local_env()
    local_dir = Path(args.local_dir).resolve()
    revision = "local"

    expected_files: list[str] = []
    if not args.skip_download:
        import os

        revision, expected_files = download_snapshot(
            args.repo_id,
            local_dir=local_dir,
            allow_patterns=["real/*.flac", "fake/*.flac"],
            token=os.getenv("HF_TOKEN"),  # public dataset; token only lifts rate limits
        )

    fake_files = sorted((local_dir / "fake").glob("*.flac"))
    real_files = sorted((local_dir / "real").glob("*.flac"))
    if not fake_files or not real_files:
        raise SystemExit(
            f"Expected real/ and fake/ FLAC files under {local_dir}. "
            "Run without --skip-download, or point --local-dir at an existing copy."
        )
    print(f"found {len(real_files)} real and {len(fake_files)} fake clips")
    if expected_files:
        expected_real = sum(1 for n in expected_files if n.startswith("real/"))
        expected_fake = sum(1 for n in expected_files if n.startswith("fake/"))
        if len(real_files) != expected_real or len(fake_files) != expected_fake:
            raise SystemExit(
                f"Partial dataset: have {len(real_files)}/{expected_real} real and "
                f"{len(fake_files)}/{expected_fake} fake clips. Ingesting this would skew the "
                "label balance. Re-run to finish the download."
            )

    writer = ClipWriter(
        source_dataset=args.name,
        license_or_consent=args.license_or_consent,
        output_root=Path(args.output_root),
        min_duration_s=args.min_duration,
        max_duration_s=args.max_duration,
    )

    generator_counts: Counter[str] = Counter()
    for path in fake_files:
        prefix, source_id = parse_stem(path.stem)
        generator = GENERATORS.get(prefix)
        if generator is None:
            raise SystemExit(
                f"Unknown generator prefix {prefix!r} in {path.name}. Update GENERATORS "
                "before ingesting, otherwise the generator holdout would be wrong."
            )
        if args.max_per_generator and generator_counts[generator] >= args.max_per_generator:
            continue
        # Speaker identity is the synthetic voice, keyed by generator + voice id.
        if writer.add_file(
            path,
            stem=path.stem,
            label="spoof",
            speaker_id=f"{generator}_{source_id}",
            language="en",
            attack_family="tts",
            generator=generator,
            subdir=f"spoof/{generator}",
        ):
            generator_counts[generator] += 1

    real_kept = 0
    speaker_counts: Counter[str] = Counter()
    for path in real_files:
        if args.max_real and real_kept >= args.max_real:
            break
        prefix, source_id = parse_stem(path.stem)
        if prefix != "yt":
            raise SystemExit(f"Unexpected real-clip prefix {prefix!r} in {path.name}")
        speaker = f"yt_{source_id}"
        if writer.add_file(
            path,
            stem=path.stem,
            label="bonafide",
            speaker_id=speaker,
            language="en",
            subdir="bonafide",
        ):
            speaker_counts[speaker] += 1
            real_kept += 1

    print(f"\nreal clips grouped into {len(speaker_counts)} YouTube source speakers")
    print(f"spoof clips per generator: {dict(sorted(generator_counts.items()))}")
    print("\n" + writer.summary())
    writer.write_candidate(
        {
            "repo_id": args.repo_id,
            "revision": revision,
            "local_dir": str(local_dir),
            "generator_prefix_map": GENERATORS,
            "spoof_per_generator": dict(generator_counts),
            "real_speakers": len(speaker_counts),
        },
        name=args.name,
    )


if __name__ == "__main__":
    main()
