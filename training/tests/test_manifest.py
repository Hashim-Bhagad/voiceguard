"""Split discipline in scripts/build_manifest.py, on a synthetic candidate set."""
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

TRAINING_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING_ROOT))
from src.ingest import CANDIDATE_COLUMNS  # noqa: E402

ok = 0
fail = 0


def check(name, condition, detail=""):
    global ok, fail
    if condition:
        ok += 1
        print(f"  PASS  {name}")
    else:
        fail += 1
        print(f"  FAIL  {name}  {detail}")


def row(path, label, generator, language, speaker, source, family):
    return {
        "clip_path": path, "label": label, "attack_family": family, "generator": generator,
        "language": language, "speaker_id": speaker, "codec": "source",
        "noise_condition": "source", "source_dataset": source,
        "license_or_consent": "test", "duration_s": 3.0,
    }


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / "candidates").mkdir()
    (root / "audio").mkdir()
    wav = (np.random.default_rng(0).standard_normal(48000) * 0.05).astype(np.float32)
    rows = []

    def add(name, *args):
        path = f"audio/{name}.wav"
        sf.write(root / path, wav, 16000)
        rows.append(row(path, *args))

    # In-the-Wild-like: each celebrity has real AND (unlabelled-generator) fake clips.
    for s in range(30):
        for k in range(3):
            add(f"itw_b_{s}_{k}", "bonafide", "none", "en", f"itw:celeb{s}", "in_the_wild", "none")
        add(f"itw_s_{s}", "spoof", "in_the_wild_unknown", "en", f"itw:celeb{s}", "in_the_wild",
            "in_the_wild")
    # Clones of Indic bona-fide speakers, same speaker ids.
    for s in range(30):
        for k in range(2):
            add(f"iv_b_{s}_{k}", "bonafide", "none", "hi", f"indicvoices:S{s}", "indicvoices", "none")
        add(f"iv_c_{s}", "spoof", "indicf5_clone", "hi", f"indicvoices:S{s}", "clones", "clone")
    # Ordinary per-generator spoofs.
    for gen in ("polly", "elevenlabs", "speechify"):
        for k in range(10):
            add(f"{gen}_{k}", "spoof", gen, "en", f"gs:{gen}_{k}", "garystafford", "tts")
    # Conflict: a held-out TEST generator shares a speaker id with bona-fide clips.
    for k in range(5):
        add(f"x_b_{k}", "bonafide", "none", "en", "gs:shared", "garystafford", "none")
    add("x_s_0", "spoof", "speechify", "en", "gs:shared", "garystafford", "tts")

    pd.DataFrame(rows, columns=CANDIDATE_COLUMNS).to_csv(root / "candidates" / "all.csv", index=False)
    out = root / "metadata.csv"
    result = subprocess.run(
        [sys.executable, str(TRAINING_ROOT / "scripts" / "build_manifest.py"),
         "--candidates-dir", str(root / "candidates"), "--out", str(out),
         "--dev-generators", "elevenlabs", "--test-generators", "speechify"],
        capture_output=True, text=True, cwd=str(TRAINING_ROOT),
    )
    check("build_manifest runs", result.returncode == 0, result.stdout[-1500:] + result.stderr[-1500:])
    df = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=CANDIDATE_COLUMNS + ["split"])

    print("== speaker-disjoint ==")
    per_speaker = df.groupby("speaker_id").split.nunique()
    check("every speaker is in exactly one split", (per_speaker == 1).all(),
          per_speaker[per_speaker > 1].to_dict())

    print("== generator holdout is never undone ==")
    check("all speechify clips stay in test", set(df[df.generator == "speechify"].split) == {"test"})
    check("all elevenlabs clips stay in dev", set(df[df.generator == "elevenlabs"].split) == {"dev"})
    check("all polly clips stay in train", set(df[df.generator == "polly"].split) == {"train"})
    shared = df[df.speaker_id == "gs:shared"]
    check("bona-fide clips follow their speaker's held-out spoof into test",
          set(shared.split) == {"test"}, shared.split.value_counts().to_dict())

    print("== speaker-split generators ==")
    itw = df[df.generator == "in_the_wild_unknown"]
    check("In-the-Wild spoofs land in train AND test (split by speaker)",
          {"train", "test"} <= set(itw.split), itw.split.value_counts().to_dict())
    clones = df[df.generator == "indicf5_clone"]
    bona_split = df[(df.label == "bonafide")].groupby("speaker_id").split.first()
    check("each clone sits in the same split as its speaker's real clips",
          (clones.split.to_numpy() == clones.speaker_id.map(bona_split).to_numpy()).all())

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
