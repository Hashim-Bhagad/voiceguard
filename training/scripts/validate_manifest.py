"""Validate VoiceGuard's speaker/generator-disjoint AASIST-L manifest before training."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))

from src.dataset import assert_no_leakage, load_metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata-csv", default="data/metadata.csv")
    parser.add_argument("--check-files", action="store_true")
    args = parser.parse_args()
    df = load_metadata(args.metadata_csv)
    assert_no_leakage(df)
    if args.check_files:
        missing = [path for path in df.clip_path if not Path(path).is_file()]
        if missing:
            raise FileNotFoundError(f"{len(missing)} clips are missing; first: {missing[0]}")
    print(df.groupby(["split", "label", "language"]).size().to_string())
    print("Manifest is valid for AASIST-L training.")


if __name__ == "__main__":
    main()
