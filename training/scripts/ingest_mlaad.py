"""Ingest real Hindi (or other) TTS spoof clips from MLAAD.

MLAAD (Multi-Language Audio Anti-Spoofing Dataset, Muller et al.) is laid out as
``fake/<lang>/<TTS-system>/<utterance>.wav`` and covers 54 languages. Hindi has
**nine** generators, which is what makes proper generator holdout possible:

    IndicF5, Indri-TTS-0.1, OmniVoice, Ringg Squirrel TTS v1.0, Veena,
    VoxCPM2, Voxtral, bark (multilingual), xtts_v2 (multilingual)

MLAAD is spoof-only; bona-fide comes from elsewhere (we use IndicVoices).

################  LICENCE WARNING  ################
MLAAD is CC-BY-NC-4.0 and ships NOTICE_NO_COMMERCIAL_USE.txt. A model trained on
it inherits that restriction. Fine for research, coursework and internal
evaluation. NOT usable in a commercial product -- for that you must generate
equivalent Hindi spoof from systems you are licensed to use.
###################################################

Two leakage hazards this script handles explicitly:

1. **Shared source text.** Every generator synthesises the *same* utterance list,
   so utterance X exists nine times. If X-by-generator-A lands in train and
   X-by-generator-B in test, the splits share content. ``--disjoint-source-text``
   (default on) gives each generator a disjoint slice of utterances, so no source
   utterance is ever reused across generators.

2. **Channel mismatch.** MLAAD is clean, read, studio-quality TTS. If your
   bona-fide side is only phone-recorded spontaneous speech (e.g. IndicVoices),
   a detector can separate the classes on channel alone and never learn a
   synthesis artifact. Mitigate by also generating same-channel spoof from your
   bona-fide corpus (scripts/make_vocoded_spoof.py) and by comparing per-generator
   FNR in eval.py: if MLAAD generators score far better than same-channel spoof,
   the model is keying on channel.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))

from src.ingest import (  # noqa: E402
    ClipWriter, download_files, list_repo_dir, load_local_env, retry,
)

REPO_ID = "mueller91/MLAAD"

# Tidy the long upstream directory names into stable generator tags.
GENERATOR_ALIASES = {
    "tts_models_multilingual_multi-dataset_bark": "bark",
    "tts_models_multilingual_multi-dataset_xtts_v2": "xtts_v2",
    "tts_models_multilingual_multi-dataset_xtts_v1.1": "xtts_v1_1",
    "Ringg Squirrel TTS v1.0": "ringg_squirrel",
    "Indri-TTS-0.1": "indri_tts",
    "ElevenLabs-v2-Multilingual": "elevenlabs_v2_multi",
    "ElevenLabs-v3": "elevenlabs_v3",
}


def generator_tag(directory_name: str) -> str:
    if directory_name in GENERATOR_ALIASES:
        return GENERATOR_ALIASES[directory_name]
    return directory_name.lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def utterance_bucket(stem: str, buckets: int) -> int:
    """Stable bucket for a source utterance, independent of PYTHONHASHSEED."""
    digest = hashlib.blake2b(stem.encode(), digest_size=4).digest()
    return int.from_bytes(digest, "big") % buckets


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo-id", default=REPO_ID)
    parser.add_argument(
        "--languages", nargs="+", default=["hi"],
        help="MLAAD language dirs, e.g. hi mr ta bn kn ml ur",
    )
    parser.add_argument(
        "--max-per-generator", type=int, default=220,
        help="Clips per (language, generator). 9 Hindi generators x 220 ~ 2000 clips.",
    )
    parser.add_argument(
        "--disjoint-source-text", dest="disjoint", action="store_true", default=True,
        help="Give each generator a disjoint slice of source utterances (default)",
    )
    parser.add_argument(
        "--allow-shared-source-text", dest="disjoint", action="store_false",
        help="Permit the same source utterance across generators (adds content leakage)",
    )
    parser.add_argument("--min-duration", type=float, default=1.5)
    parser.add_argument("--max-duration", type=float, default=15.0)
    parser.add_argument(
        "--local-dir", default=str(TRAINING_ROOT / "data" / "sources" / "mlaad"),
    )
    parser.add_argument("--output-root", default=str(TRAINING_ROOT / "data"))
    parser.add_argument("--name", default="mlaad")
    parser.add_argument(
        "--accept-noncommercial", action="store_true",
        help="Acknowledge the CC-BY-NC-4.0 restriction (required to run)",
    )
    args = parser.parse_args()

    if not args.accept_noncommercial:
        raise SystemExit(
            "MLAAD is CC-BY-NC-4.0 (non-commercial). Any model trained on it inherits that\n"
            "restriction and cannot be shipped commercially.\n\n"
            "Re-run with --accept-noncommercial once you have confirmed that is acceptable\n"
            "for this project, or generate your own Hindi spoof instead."
        )

    load_local_env()
    import os

    token = os.getenv("HF_TOKEN")
    if not token:
        raise SystemExit(
            "HF_TOKEN is not set. MLAAD is gated: accept its terms at\n"
            f"  https://huggingface.co/datasets/{args.repo_id}\n"
            "then put HF_TOKEN in training/.env."
        )

    from huggingface_hub import HfApi

    revision = retry(
        lambda: HfApi(token=token).dataset_info(args.repo_id).sha, what="MLAAD dataset_info"
    )
    print(f"{args.repo_id} @ {revision}")
    print("licence: CC-BY-NC-4.0 (non-commercial) -- acknowledged via --accept-noncommercial\n")

    local_dir = Path(args.local_dir).resolve()
    writer = ClipWriter(
        source_dataset=args.name,
        license_or_consent="CC-BY-NC-4.0 NON-COMMERCIAL (MLAAD)",
        output_root=Path(args.output_root),
        min_duration_s=args.min_duration,
        max_duration_s=args.max_duration,
    )

    selected: list[str] = []
    plan: dict[str, list[str]] = {}
    for language in args.languages:
        entries = list_repo_dir(args.repo_id, f"fake/{language}", token)
        generator_dirs = sorted(
            e["path"].split("/")[-1] for e in entries if e["type"] == "directory"
        )
        if not generator_dirs:
            raise SystemExit(
                f"No generator directories under fake/{language} in {args.repo_id}. "
                f"Check the language code."
            )
        print(f"[{language}] {len(generator_dirs)} generators: "
              f"{[generator_tag(g) for g in generator_dirs]}")

        for index, generator in enumerate(generator_dirs):
            files = [
                e["path"] for e in list_repo_dir(args.repo_id, f"fake/{language}/{generator}", token)
                if e["type"] == "file" and e["path"].lower().endswith((".wav", ".flac"))
            ]
            files.sort()
            if args.disjoint:
                # Each generator keeps only utterances in its own hash bucket, so
                # no source utterance appears under two generators.
                files = [
                    f for f in files
                    if utterance_bucket(Path(f).stem, len(generator_dirs)) == index
                ]
            chosen = files[: args.max_per_generator]
            plan[f"{language}/{generator}"] = chosen
            selected.extend(chosen)
            print(f"    {generator_tag(generator):22s} {len(chosen):4d} selected "
                  f"(of {len(files)} eligible)")

    if not selected:
        raise SystemExit("Nothing selected; check --max-per-generator and the language codes.")
    print(f"\ndownloading {len(selected)} files ...")
    download_files(
        args.repo_id, files=selected, local_dir=local_dir, token=token, revision=revision
    )

    print("\nnormalising to 16 kHz mono WAV ...")
    per_generator: Counter[str] = Counter()
    for key, files in plan.items():
        language, generator = key.split("/", 1)
        tag = generator_tag(generator)
        for remote in files:
            stem = Path(remote).stem
            if writer.add_file(
                local_dir / remote,
                stem=f"{language}_{tag}_{stem}",
                label="spoof",
                # speaker_id == generator keeps the speaker split aligned with the
                # generator holdout that build_manifest.py applies.
                speaker_id=tag,
                language=language,
                attack_family="tts",
                generator=tag,
                codec="studio",
                noise_condition="clean",
                subdir=f"spoof/{language}/{tag}",
            ):
                per_generator[f"{language}:{tag}"] += 1

    print(f"\nper generator: {dict(sorted(per_generator.items()))}")
    print(writer.summary())
    writer.write_candidate(
        {
            "repo_id": args.repo_id,
            "revision": revision,
            "languages": args.languages,
            "max_per_generator": args.max_per_generator,
            "disjoint_source_text": args.disjoint,
            "per_generator": dict(per_generator),
            "licence": "CC-BY-NC-4.0, non-commercial; NOTICE_NO_COMMERCIAL_USE.txt applies",
            "citation": "Muller et al., MLAAD: The Multi-Language Audio Anti-Spoofing Dataset",
            "channel_caveat": (
                "Clean read studio TTS. Pair with same-channel spoof (make_vocoded_spoof.py) "
                "so the model cannot separate classes on channel alone."
            ),
        },
        name=args.name,
    )


if __name__ == "__main__":
    main()
