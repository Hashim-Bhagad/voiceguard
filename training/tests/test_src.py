"""Behavioural checks for the reworked src/dataset.py and src/model.py."""
import sys
import tempfile
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf
import torch
import yaml

TRAINING_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING_ROOT))
from src.dataset import (  # noqa: E402
    Augmenter, SpoofDataset, assert_no_leakage, balanced_sample_weights,
    load_metadata, read_audio, repeat_pad, take_window,
)
from src.model import build_model  # noqa: E402

import random  # noqa: E402

ok = 0
fail = 0


def check(name, condition, detail=""):
    global ok, fail
    if condition:
        ok += 1
        print(f"  PASS  {name}")
    else:
        fail += 1
        print(f"  FAIL  {name} {detail}")


print("== repeat_pad vs old zero-pad behaviour ==")
short = np.linspace(-0.5, 0.5, 1000, dtype=np.float32)
padded = repeat_pad(short, 64600)
check("length is exact", len(padded) == 64600)
check("no silent tail (this was the bug)", float(np.abs(padded[-500:]).mean()) > 0.01,
      f"tail mean={float(np.abs(padded[-500:]).mean()):.6f}")
check("tiles the source", np.allclose(padded[:1000], short))
check("matches upstream np.tile semantics",
      np.allclose(padded, np.tile(short, int(np.ceil(64600 / 1000)))[:64600]))

print("== take_window ==")
long_sig = np.random.default_rng(0).standard_normal(100000).astype(np.float32)
centre = take_window(long_sig, 64600, train=False, rng=random.Random(1))
centre2 = take_window(long_sig, 64600, train=False, rng=random.Random(999))
check("eval crop is deterministic + centred", np.array_equal(centre, centre2))
check("eval crop is actually the centre",
      np.array_equal(centre, long_sig[(100000 - 64600) // 2:][:64600]))
crops = {take_window(long_sig, 64600, True, random.Random(s)).tobytes()[:64] for s in range(8)}
check("train crop varies", len(crops) > 1, f"unique={len(crops)}")

print("== Augmenter fallbacks warn instead of silently no-oping ==")
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    aug = Augmenter(
        {"narrowband_prob": 1.0, "noise_prob": 1.0, "rir_prob": 1.0,
         "noise_dir": "data/augmentation/musan", "rir_dir": "data/augmentation/rirs"},
        16000,
    )
    messages = [str(w.message) for w in caught]
check("warns about missing noise_dir", any("noise_dir" in m for m in messages), messages)
check("warns about missing rir_dir", any("rir_dir" in m for m in messages), messages)
clean = np.sin(2 * np.pi * 440 * np.arange(64600) / 16000).astype(np.float32) * 0.5
augmented = aug(clean.copy(), random.Random(0), np.random.default_rng(0))
check("augmentation changed the signal", not np.allclose(augmented, clean))
check("augmentation preserved length", len(augmented) == 64600)
check("augmentation stayed in range", float(np.max(np.abs(augmented))) <= 1.0 + 1e-6)

print("== manifest validation ==")
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    audio = root / "audio"
    audio.mkdir()
    rng = np.random.default_rng(0)

    def make(name, seconds):
        path = audio / name
        sf.write(path, rng.standard_normal(int(16000 * seconds)).astype(np.float32) * 0.1, 16000)
        return f"audio/{name}"

    rows = []
    plan = [
        ("train", "bonafide", "none", "none", "hi", "iv_s1", 5.0),
        ("train", "bonafide", "none", "none", "en", "yt_0001", 3.0),
        ("train", "spoof", "tts", "polly", "en", "src_a", 1.5),
        ("dev", "bonafide", "none", "none", "hi", "iv_s2", 4.0),
        ("dev", "spoof", "tts", "elevenlabs", "en", "src_b", 6.0),
        ("test", "bonafide", "none", "none", "ta", "iv_s3", 4.0),
        ("test", "spoof", "tts", "speechify", "en", "src_c", 2.0),
    ]
    for i, (split, label, fam, gen, lang, spk, dur) in enumerate(plan):
        rows.append({
            "clip_path": make(f"c{i}.wav", dur), "label": label, "attack_family": fam,
            "generator": gen, "language": lang, "speaker_id": spk, "split": split,
        })
    df_raw = pd.DataFrame(rows)
    csv = root / "metadata.csv"
    df_raw.to_csv(csv, index=False)

    df = load_metadata(csv)
    check("clip paths resolved to absolute", all(Path(p).is_absolute() for p in df.clip_path))
    assert_no_leakage(df)
    check("clean manifest passes leakage checks", True)

    # speaker leakage
    bad = df_raw.copy()
    bad.loc[bad.split == "dev", "speaker_id"] = "iv_s1"
    bad.to_csv(csv, index=False)
    try:
        assert_no_leakage(load_metadata(csv))
        check("detects speaker leakage", False, "no error raised")
    except ValueError as exc:
        check("detects speaker leakage", "speaker leakage" in str(exc))

    # generator holdout
    bad = df_raw.copy()
    bad.loc[bad.label == "spoof", "generator"] = "polly"
    bad.to_csv(csv, index=False)
    try:
        assert_no_leakage(load_metadata(csv))
        check("detects missing unseen generator", False, "no error raised")
    except ValueError as exc:
        check("detects missing unseen generator", "unseen in train" in str(exc))

    # duplicate clip paths
    bad = pd.concat([df_raw, df_raw.iloc[[0]]], ignore_index=True)
    bad.to_csv(csv, index=False)
    try:
        load_metadata(csv)
        check("detects duplicate clip_path", False, "no error raised")
    except ValueError as exc:
        check("detects duplicate clip_path", "duplicate clip_path" in str(exc))

    df_raw.to_csv(csv, index=False)
    df = load_metadata(csv)

    print("== SpoofDataset ==")
    cache = root / "cache"
    ds = SpoofDataset(df, "train", 16000, 64600, train=True,
                      augmentation={"narrowband_prob": 0.5, "noise_prob": 0.5, "rir_prob": 0.2},
                      cache_dir=cache, seed=42)
    x, y = ds[0]
    check("train item shape", tuple(x.shape) == (64600,), tuple(x.shape))
    check("train item dtype", x.dtype == torch.float32)
    check("label is long", y.dtype == torch.int64)
    check("cache files written", any(cache.rglob("*.npy")))

    ev = SpoofDataset(df, "test", 16000, 64600, train=False, cache_dir=cache, seed=42)
    a, _ = ev[0]
    b, _ = ev[0]
    check("eval item reproducible", torch.equal(a, b))

    short_row = df[df.clip_path.str.endswith("c2.wav")]
    check("1.5 s clip exists in manifest", len(short_row) == 1)
    raw_short = read_audio(short_row.iloc[0].clip_path, 16000)
    check("short clip really is shorter than the window", len(raw_short) < 64600)
    ds_short = SpoofDataset(df[df.clip_path == short_row.iloc[0].clip_path].assign(split="test"),
                            "test", 16000, 64600, train=False)
    xs, _ = ds_short[0]
    check("short clip has no silent tail after fix",
          float(xs[-1000:].abs().mean()) > 0.001, f"tail={float(xs[-1000:].abs().mean()):.6f}")

    print("== balanced_sample_weights ==")
    w = balanced_sample_weights(df, "train", ("label", "language"))
    check("one weight per row", len(w) == 3, len(w))
    check("all weights positive", bool(np.all(w > 0)))

print("== model ==")
CONFIG_PATH = TRAINING_ROOT / "configs" / "aasist_l.yaml"
WEIGHTS_PATH = TRAINING_ROOT / "weights" / "AASIST-L.pth"

cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
model = build_model(cfg)
check("param count guard passes", model.num_parameters() == 85306, model.num_parameters())
if WEIGHTS_PATH.is_file():
    miss, unexp = model.load_pretrained(WEIGHTS_PATH)
    check("pretrained loads strictly", not miss and not unexp, f"{len(miss)}/{len(unexp)}")
else:
    print(f"  SKIP  pretrained load ({WEIGHTS_PATH} absent; run scripts/resolve_pretrained.py)")

bad_cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
bad_cfg["model"]["architecture"]["gat_dims"] = [64, 32]  # this is full AASIST, not AASIST-L
try:
    build_model(bad_cfg)
    check("rejects non-AASIST-L architecture", False, "no error raised")
except ValueError as exc:
    check("rejects non-AASIST-L architecture", "does not match the official AASIST-L" in str(exc))

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
