"""Combine candidate CSVs into data/metadata.csv with disciplined splits.

This replaces the old assemble_full_manifest.py, which required every ingest step
to pre-assign its own train/dev/test split and then merely *checked* for speaker
leakage afterwards. That is backwards: with several sources you cannot pick a
per-source split that happens to keep speakers disjoint and generators held out
globally. Here the split is assigned once, over the pooled data, under three
constraints:

1. Speaker-disjoint. A speaker's clips all land in exactly one split. Otherwise
   the model can recognise the voice instead of the artifacts.
2. Generator holdout. Whole TTS/VC families are reserved for dev and test, so the
   reported EER measures generalisation to an unseen synthesiser rather than
   in-generator recall.
3. Per-language label coverage. Reported so you can see immediately whether a
   language appears on only one side of the decision, which is the confound that
   makes a multilingual detector learn language ID instead of spoofing.

Splitting is deterministic given --seed.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))

from src.dataset import assert_no_leakage, load_metadata  # noqa: E402
from src.ingest import CANDIDATE_COLUMNS  # noqa: E402

MANIFEST_COLUMNS = CANDIDATE_COLUMNS + ["split"]


def assign_generator_holdout(
    df: pd.DataFrame, dev_generators: list[str], test_generators: list[str]
) -> dict[str, str]:
    """Map each spoof generator to 'train', 'dev' or 'test'."""
    available = sorted(
        g for g in df.loc[df.label == "spoof", "generator"].unique() if str(g) != "none"
    )
    if not available:
        raise SystemExit("No spoof generators found in the candidate CSVs.")

    chosen: dict[str, str] = {}
    for name, target in ((dev_generators, "dev"), (test_generators, "test")):
        for generator in name:
            if generator not in available:
                raise SystemExit(
                    f"Requested holdout generator {generator!r} is not present.\n"
                    f"  available: {available}"
                )
            if generator in chosen:
                raise SystemExit(f"Generator {generator!r} cannot be held out for two splits.")
            chosen[generator] = target
    for generator in available:
        chosen.setdefault(generator, "train")

    if not any(v == "dev" for v in chosen.values()) or not any(
        v == "test" for v in chosen.values()
    ):
        raise SystemExit(
            "Both dev and test need at least one held-out generator. Available generators:\n"
            f"  {available}\n"
            "Pass --dev-generators / --test-generators explicitly."
        )
    if not any(v == "train" for v in chosen.values()):
        raise SystemExit("Every generator was held out, leaving no spoof data to train on.")
    return chosen


def split_speakers(
    speakers: list[str], ratios: tuple[float, float, float], rng: np.random.Generator
) -> dict[str, str]:
    """Deterministically assign whole speakers to splits."""
    ordered = sorted(speakers)
    rng.shuffle(ordered)
    total = len(ordered)
    n_train = int(round(total * ratios[0]))
    n_dev = int(round(total * ratios[1]))
    # Guarantee every split gets at least one speaker when there are enough to go round.
    if total >= 3:
        n_train = min(max(n_train, 1), total - 2)
        n_dev = min(max(n_dev, 1), total - n_train - 1)
    assignment = {}
    for index, speaker in enumerate(ordered):
        if index < n_train:
            assignment[speaker] = "train"
        elif index < n_train + n_dev:
            assignment[speaker] = "dev"
        else:
            assignment[speaker] = "test"
    return assignment


def cap_per_group(
    df: pd.DataFrame, limit: int, by: list[str], rng_seed: int
) -> pd.DataFrame:
    if limit <= 0:
        return df
    return (
        df.groupby(by, group_keys=False)
        .apply(lambda g: g.sample(n=min(len(g), limit), random_state=rng_seed), include_groups=True)
        .reset_index(drop=True)
    )


def report(df: pd.DataFrame) -> None:
    print("\n=== clips per split and label ===")
    print(df.groupby(["split", "label"]).size().unstack(fill_value=0).to_string())

    print("\n=== clips per split, language and label ===")
    table = df.groupby(["split", "language", "label"]).size().unstack(fill_value=0)
    for column in ("bonafide", "spoof"):
        if column not in table:
            table[column] = 0
    print(table[["bonafide", "spoof"]].to_string())

    print("\n=== spoof generators per split ===")
    for split in ("train", "dev", "test"):
        rows = df[(df.split == split) & (df.label == "spoof")]
        counts = rows.generator.value_counts().to_dict()
        print(f"  {split:5s} {counts}")

    print("\n=== hours per split ===")
    if "duration_s" in df:
        hours = df.groupby("split").duration_s.sum() / 3600.0
        for split, value in hours.items():
            print(f"  {split:5s} {value:.2f} h")

    print("\n=== language / label coverage warnings ===")
    problems = 0
    for language, group in df.groupby("language"):
        labels = set(group.label)
        if labels != {"bonafide", "spoof"}:
            only = labels.pop() if labels else "nothing"
            problems += 1
            print(
                f"  ! {language}: only '{only}' present ({len(group)} clips). The model can key on "
                f"language instead of artifacts for {language}."
            )
    for split in ("train", "dev", "test"):
        for language, group in df[df.split == split].groupby("language"):
            if len(set(group.label)) < 2 and len(group) > 0:
                problems += 1
                print(
                    f"  ~ {split}/{language}: single-label ({sorted(set(group.label))}, "
                    f"{len(group)} clips)"
                )
    if not problems:
        print("  none: every language appears as both bona-fide and spoof in every split")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--candidates-dir", default=str(TRAINING_ROOT / "data" / "candidates"))
    parser.add_argument("--out", default=str(TRAINING_ROOT / "data" / "metadata.csv"))
    parser.add_argument(
        "--dev-generators", nargs="*", default=["elevenlabs"],
        help="Spoof generators reserved for dev (unseen during training)",
    )
    parser.add_argument(
        "--test-generators", nargs="*", default=["speechify", "in_the_wild_unknown"],
        help="Spoof generators reserved for test (unseen during training)",
    )
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--dev-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--max-per-source-label", type=int, default=0,
        help="Optional cap on clips per (source_dataset, label) to bound CPU epoch time",
    )
    parser.add_argument("--check-files", action="store_true")
    parser.add_argument(
        "--allow-shared-generators", action="store_true",
        help="Skip the unseen-generator requirement. Only for a quick smoke test.",
    )
    args = parser.parse_args()

    candidate_dir = Path(args.candidates_dir).resolve()
    files = sorted(candidate_dir.glob("*.csv"))
    if not files:
        raise SystemExit(
            f"No candidate CSVs in {candidate_dir}. Run the scripts/ingest_*.py steps first."
        )

    frames = []
    for path in files:
        frame = pd.read_csv(path)
        missing = set(CANDIDATE_COLUMNS) - set(frame.columns)
        if missing:
            raise SystemExit(f"{path.name} is missing columns: {sorted(missing)}")
        if "split" in frame.columns:
            raise SystemExit(
                f"{path.name} already has a 'split' column. Candidate CSVs must not assign "
                "splits; this script does that globally."
            )
        print(f"  {path.name}: {len(frame)} rows")
        frames.append(frame[CANDIDATE_COLUMNS])

    df = pd.concat(frames, ignore_index=True)
    df["label"] = df.label.astype(str).str.lower().str.strip()
    df["generator"] = df.generator.fillna("none").astype(str).str.strip().str.lower()
    df["language"] = df.language.fillna("unknown").astype(str).str.strip()
    df["speaker_id"] = df.speaker_id.astype(str).str.strip()

    before = len(df)
    df = df.drop_duplicates(subset=["clip_path"]).reset_index(drop=True)
    if len(df) != before:
        print(f"  dropped {before - len(df)} duplicate clip_path rows")

    if args.max_per_source_label:
        df = cap_per_group(df, args.max_per_source_label, ["source_dataset", "label"], args.seed)
        print(f"  capped to {args.max_per_source_label} per (source_dataset, label): {len(df)} rows")

    rng = np.random.default_rng(args.seed)

    # --- spoof rows follow their generator's holdout assignment -------------
    generator_split = assign_generator_holdout(df, args.dev_generators, args.test_generators)
    print("\ngenerator -> split")
    for generator, split in sorted(generator_split.items()):
        print(f"  {generator:24s} {split}")

    df["split"] = pd.NA
    spoof_mask = df.label == "spoof"
    df.loc[spoof_mask, "split"] = df.loc[spoof_mask, "generator"].map(generator_split)

    # --- bona-fide rows are split by speaker, per language ------------------
    ratios = (args.train_ratio, args.dev_ratio, 1.0 - args.train_ratio - args.dev_ratio)
    if min(ratios) <= 0:
        raise SystemExit(f"Invalid split ratios {ratios}; they must all be positive.")
    bona_mask = df.label == "bonafide"
    speaker_assignment: dict[str, str] = {}
    for language, group in df[bona_mask].groupby("language"):
        assignment = split_speakers(list(group.speaker_id.unique()), ratios, rng)
        speaker_assignment.update(assignment)
        counts: dict[str, int] = defaultdict(int)
        for split in assignment.values():
            counts[split] += 1
        print(f"  bona-fide {language}: {len(assignment)} speakers -> {dict(counts)}")
    df.loc[bona_mask, "split"] = df.loc[bona_mask, "speaker_id"].map(speaker_assignment)

    unassigned = int(df.split.isna().sum())
    if unassigned:
        raise SystemExit(f"{unassigned} rows could not be assigned a split (internal error).")

    # A spoof speaker must not also appear as a bona-fide speaker in another split.
    conflicts = []
    for speaker, group in df.groupby("speaker_id"):
        if group.split.nunique() > 1:
            conflicts.append((speaker, sorted(set(group.split))))
    if conflicts:
        print(f"\n  resolving {len(conflicts)} speakers that straddled splits")
        for speaker, _ in conflicts:
            # Send every clip of the speaker to the split holding most of them.
            rows = df.speaker_id == speaker
            winner = df.loc[rows, "split"].value_counts().idxmax()
            df.loc[rows, "split"] = winner

    output = Path(args.out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    df = df[MANIFEST_COLUMNS].sort_values(
        ["split", "label", "language", "clip_path"]
    ).reset_index(drop=True)
    df.to_csv(output, index=False)

    report(df)

    print(f"\nwrote {output} ({len(df)} rows)")
    provenance = output.with_suffix(".build.json")
    provenance.write_text(
        json.dumps(
            {
                "candidates": [p.name for p in files],
                "rows": len(df),
                "seed": args.seed,
                "ratios": {"train": ratios[0], "dev": ratios[1], "test": ratios[2]},
                "generator_split": generator_split,
                "dev_generators": args.dev_generators,
                "test_generators": args.test_generators,
                "max_per_source_label": args.max_per_source_label,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {provenance}")

    # Validate through exactly the same code path training will use.
    validated = load_metadata(output)
    if args.check_files:
        missing = [p for p in validated.clip_path if not Path(p).is_file()]
        if missing:
            raise SystemExit(f"{len(missing)} clips are missing; first: {missing[0]}")
        print(f"verified {len(validated)} audio files exist")
    assert_no_leakage(validated, require_unseen_generator=not args.allow_shared_generators)
    print("manifest passes speaker-disjointness and generator-holdout checks")


if __name__ == "__main__":
    main()
