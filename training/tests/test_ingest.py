"""Checks for the ingest layer that need no network access."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

TRAINING_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING_ROOT))

from src.ingest import (  # noqa: E402
    CANDIDATE_COLUMNS, ClipWriter, normalise_language, safe_name, to_mono_16k,
)

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


def load_script(filename: str):
    path = TRAINING_ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


print("== language normalisation ==")
check("hindi -> hi", normalise_language("hindi") == "hi")
check("Marathi -> mr", normalise_language("Marathi") == "mr")
check("ta stays ta", normalise_language("ta") == "ta")
check("Indian English -> en-IN", normalise_language("Indian English") == "en-IN")
check("english -> en", normalise_language("english") == "en")
check("unknown passes through", normalise_language("klingon") == "klingon")
check("empty -> unknown", normalise_language("") == "unknown")

print("== safe_name ==")
check("strips separators", safe_name("a/b c:d") == "a_b_c_d", safe_name("a/b c:d"))
check("keeps dots and dashes", safe_name("yt_0001-part.001") == "yt_0001-part.001")

print("== to_mono_16k ==")
stereo = np.stack([np.ones(8000), -np.ones(8000)], axis=1).astype(np.float32)
mono = to_mono_16k(stereo, 8000)
check("downmixes to mono", mono.ndim == 1)
check("resamples 8k -> 16k", abs(len(mono) - 16000) <= 64, len(mono))
check("mean of +1/-1 channels is ~0", abs(float(mono.mean())) < 1e-3)

print("== ClipWriter ==")
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    rng = np.random.default_rng(0)
    writer = ClipWriter("demo_source", "CC-BY-4.0", root, min_duration_s=1.0, max_duration_s=3.0)

    check("accepts a normal clip", writer.add(
        rng.standard_normal(16000 * 2).astype(np.float32) * 0.1, 16000,
        stem="ok_0001", label="bonafide", speaker_id="spk A", language="hindi"))
    check("rejects a too-short clip", not writer.add(
        rng.standard_normal(8000).astype(np.float32) * 0.1, 16000,
        stem="short", label="bonafide", speaker_id="spk A", language="hindi"))
    check("counted the short skip", writer.skipped_short == 1)
    check("truncates an over-long clip", writer.add(
        rng.standard_normal(16000 * 10).astype(np.float32) * 0.1, 16000,
        stem="long_0001", label="spoof", speaker_id="voice1", language="en",
        attack_family="tts", generator="elevenlabs"))
    check("truncated to max_duration", writer.rows[-1]["duration_s"] == 3.0,
          writer.rows[-1]["duration_s"])

    try:
        writer.add(rng.standard_normal(16000 * 2).astype(np.float32), 16000,
                   stem="bad", label="fake", speaker_id="x", language="en")
        check("rejects an invalid label", False, "no error raised")
    except ValueError:
        check("rejects an invalid label", True)

    row = writer.rows[0]
    check("clip_path is relative to output root", not Path(str(row["clip_path"])).is_absolute())
    check("language was normalised", row["language"] == "hi", row["language"])
    check("speaker is namespaced by source", row["speaker_id"] == "demo_source:spk_A",
          row["speaker_id"])
    check("row has exactly the schema keys", set(row) == set(CANDIDATE_COLUMNS),
          set(row) ^ set(CANDIDATE_COLUMNS))

    written = root / str(row["clip_path"])
    check("audio file exists on disk", written.is_file())
    info = sf.info(str(written))
    check("written at 16 kHz", info.samplerate == 16000, info.samplerate)
    check("written as mono", info.channels == 1, info.channels)
    check("written as 16-bit PCM", info.subtype == "PCM_16", info.subtype)

    path = writer.write_candidate({"note": "unit test"}, name="demo")
    check("candidate csv written", path.is_file())
    check("provenance sidecar written", path.with_suffix(".source.json").is_file())
    df = pd.read_csv(path)
    check("csv columns match schema", list(df.columns) == CANDIDATE_COLUMNS, list(df.columns))
    # Two rows: the 2 s bona-fide clip and the truncated spoof clip. The short
    # clip and the invalid-label clip must not have been recorded.
    check("csv row count matches accepted clips", len(df) == 2, len(df))

    empty = ClipWriter("empty_source", "CC-BY-4.0", root)
    try:
        empty.write_candidate({})
        check("refuses to write an empty candidate", False, "no error raised")
    except RuntimeError:
        check("refuses to write an empty candidate", True)

print("== garystafford filename parsing ==")
gs = load_script("ingest_garystafford.py")
check("parses fake stem", gs.parse_stem("el_0009_c_part_004") == ("el", "0009"))
check("parses real stem", gs.parse_stem("yt_0006_p2_part_007") == ("yt", "0006"))
check("parses plain part stem", gs.parse_stem("po_0031_part_008") == ("po", "0031"))
check("all 6 documented generators mapped", set(gs.GENERATORS) == {"po", "el", "hg", "hu", "lv", "sp"},
      set(gs.GENERATORS))
try:
    gs.parse_stem("weird-name")
    check("rejects unparseable stem", False, "no error raised")
except ValueError:
    check("rejects unparseable stem", True)

print("== in-the-wild metadata handling ==")
itw = load_script("ingest_in_the_wild.py")
check("maps bona-fide", itw.normalise_label("bona-fide") == "bonafide")
check("maps spoof", itw.normalise_label("spoof") == "spoof")
check("maps real", itw.normalise_label("Real") == "bonafide")
check("maps fake", itw.normalise_label("FAKE") == "spoof")
try:
    itw.normalise_label("maybe")
    check("rejects unknown label", False, "no error raised")
except SystemExit:
    check("rejects unknown label", True)
check("detects file column", itw.pick_column(["file", "speaker", "label"], itw.FILE_KEYS, "file") == "file")
check("detects capitalised column",
      itw.pick_column(["File", "Speaker", "Label"], itw.SPEAKER_KEYS, "speaker") == "Speaker")
try:
    itw.pick_column(["a", "b"], itw.LABEL_KEYS, "label")
    check("fails loudly on missing column", False, "no error raised")
except SystemExit:
    check("fails loudly on missing column", True)

print(f"\n{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
