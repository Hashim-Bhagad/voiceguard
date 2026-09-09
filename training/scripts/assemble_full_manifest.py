"""Combine reviewed source candidate manifests into a validated AASIST-L metadata.csv."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REQUIRED = {
    "clip_path", "label", "attack_family", "generator", "language", "speaker_id", "split",
    "codec", "noise_condition", "source_dataset", "license_or_consent",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates-dir", default="data/candidates")
    parser.add_argument("--out", default="data/metadata.csv")
    parser.add_argument("--check-files", action="store_true")
    args = parser.parse_args()
    candidate_dir = Path(args.candidates_dir).resolve()
    files = sorted(candidate_dir.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No candidate CSV files in {candidate_dir}")
    frames = []
    for path in files:
        frame = pd.read_csv(path)
        missing = REQUIRED - set(frame.columns)
        if missing:
            raise ValueError(f"{path.name} is missing: {sorted(missing)}")
        frames.append(frame)
    merged = pd.concat(frames, ignore_index=True)
    merged["label"] = merged.label.astype(str).str.lower().str.strip()
    merged["split"] = merged.split.astype(str).str.lower().str.strip()
    if set(merged.label) - {"bonafide", "spoof"}:
        raise ValueError("labels must be bonafide or spoof")
    if set(merged.split) - {"train", "dev", "test"}:
        raise ValueError("splits must be train, dev, or test")
    for split in ("train", "dev", "test"):
        labels = set(merged[merged.split == split].label)
        if labels != {"bonafide", "spoof"}:
            raise ValueError(f"{split} must contain both labels, found {labels}")
    for left, right in (("train", "dev"), ("train", "test"), ("dev", "test")):
        overlap = set(merged[merged.split == left].speaker_id) & set(merged[merged.split == right].speaker_id)
        if overlap:
            raise ValueError(f"speaker leakage {left}/{right}: {sorted(overlap)[:5]}")
    train_generators = set(merged[(merged.split == "train") & (merged.label == "spoof")].generator.astype(str).str.lower())
    for split in ("dev", "test"):
        held_out = set(merged[(merged.split == split) & (merged.label == "spoof")].generator.astype(str).str.lower()) - train_generators
        if not held_out:
            raise ValueError(f"{split} must include an unseen spoof generator")
    output = Path(args.out).resolve()
    if args.check_files:
        missing_audio = [path for path in merged.clip_path if not (output.parent / path).is_file()]
        if missing_audio:
            raise FileNotFoundError(f"Missing {len(missing_audio)} clips; first: {missing_audio[0]}")
    output.parent.mkdir(parents=True, exist_ok=True)
    merged.sort_values(["split", "label", "language", "clip_path"]).to_csv(output, index=False)
    print(merged.groupby(["split", "label", "language"]).size().to_string())
    print(f"Wrote {len(merged)} rows to {output}")


if __name__ == "__main__":
    main()
