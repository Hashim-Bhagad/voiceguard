"""Shared helpers for turning raw source datasets into VoiceGuard candidate CSVs.

Each ``scripts/ingest_*.py`` writes one CSV per source into ``data/candidates/``
describing clips it has already normalised to 16 kHz mono WAV under
``data/audio/``. Candidate CSVs deliberately do **not** carry a ``split`` column:
``scripts/build_manifest.py`` assigns splits later so that speaker-disjointness
and generator holdout are enforced globally instead of per-source.

Every row records ``source_dataset`` and ``license_or_consent`` so provenance
survives into the final manifest.
"""
from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf
import soxr

TRAINING_ROOT = Path(__file__).resolve().parents[1]
TARGET_SAMPLE_RATE = 16000

CANDIDATE_COLUMNS = [
    "clip_path",
    "label",
    "attack_family",
    "generator",
    "language",
    "speaker_id",
    "codec",
    "noise_condition",
    "source_dataset",
    "license_or_consent",
    "duration_s",
]

# Map assorted source spellings onto the tags used by the model and reports.
LANGUAGE_ALIASES = {
    "hindi": "hi", "hi": "hi",
    "marathi": "mr", "mr": "mr",
    "tamil": "ta", "ta": "ta",
    "telugu": "te", "te": "te",
    "bengali": "bn", "bn": "bn",
    "kannada": "kn", "kn": "kn",
    "malayalam": "ml", "ml": "ml",
    "gujarati": "gu", "gu": "gu",
    "punjabi": "pa", "pa": "pa",
    "urdu": "ur", "ur": "ur",
    "odia": "or", "or": "or",
    "assamese": "as", "as": "as",
    "english": "en", "en": "en", "en-us": "en", "en_us": "en",
    # normalise_language() lowercases and turns spaces into dashes before lookup,
    # so multi-word aliases must be written in dashed form.
    "en-in": "en-IN", "en_in": "en-IN", "indian-english": "en-IN",
}


def normalise_language(value: object) -> str:
    text = str(value).strip().lower().replace(" ", "-")
    return LANGUAGE_ALIASES.get(text, text or "unknown")


def safe_name(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_") or "unknown"


def load_local_env() -> None:
    """Load training/.env into os.environ without adding a dotenv dependency.

    Existing environment variables win, so an exported HF_TOKEN is not clobbered.
    """
    env_path = TRAINING_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)


# Hugging Face rate-limits free accounts to 1000 API calls per 5-minute window,
# and a dataset of thousands of small files can use that up. Retrying sooner than
# the window reset just burns the next attempt, so wait the window out.
RATE_LIMIT_WAIT_S = 310.0
MAX_STALLED_ROUNDS = 6  # rounds in a row with no new files before giving up (~30 min)


def is_rate_limited(text: str) -> bool:
    text = str(text)
    return "429" in text or "Too Many Requests" in text or "rate limit" in text.lower()


def retry(operation, *, attempts: int = 6, base_delay: float = 3.0, what: str = "download"):
    """Retry a flaky network call with exponential backoff.

    Hugging Face transfers of thousands of small files over a home connection hit
    ``ConnectionResetError`` fairly often. Both ``snapshot_download`` and
    ``hf_hub_download`` resume from the local cache, so retrying is cheap and
    does not re-fetch completed files.
    """
    import time

    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001 - any transport error is worth retrying
            if attempt == attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            if is_rate_limited(exc):
                delay = RATE_LIMIT_WAIT_S
            print(
                f"  ! {what} attempt {attempt}/{attempts} failed ({type(exc).__name__}: "
                f"{str(exc)[:160]}); resuming in {delay:.0f}s"
            )
            time.sleep(delay)
    raise AssertionError("unreachable")


def download_snapshot(
    repo_id: str,
    *,
    local_dir: Path,
    allow_patterns: list[str],
    token: str | None,
    revision: str | None = None,
    attempts: int = 8,
) -> tuple[str, list[str]]:
    """Download a dataset subset and *verify* every expected file arrived.

    This does not just wrap ``snapshot_download`` in a retry. ``huggingface_hub``
    has an offline fallback: if the API is unreachable mid-transfer it logs
    "Returning existing local_dir ... as remote repo cannot be accessed" and
    returns **successfully** with a partial download. A partial download here is
    worse than a crash, because the class balance silently shifts (we hit exactly
    this: 241 of 933 real clips, with exit code 0) and training would proceed on a
    skewed corpus.

    So we resolve the authoritative file list first, then loop until every
    expected file is present on disk.
    """
    import fnmatch
    import time

    from huggingface_hub import HfApi, snapshot_download

    api = HfApi(token=token)
    resolved = revision or retry(
        lambda: api.dataset_info(repo_id).sha, what=f"{repo_id} dataset_info"
    )
    all_files = retry(
        lambda: api.list_repo_files(repo_id, repo_type="dataset", revision=resolved),
        what=f"{repo_id} list_repo_files",
    )
    expected = sorted(
        name for name in all_files
        if any(fnmatch.fnmatch(name, pattern) for pattern in allow_patterns)
    )
    if not expected:
        raise RuntimeError(
            f"No files in {repo_id}@{resolved} match {allow_patterns}. "
            "The repository layout changed."
        )
    local_dir = Path(local_dir)
    print(f"{repo_id} @ {resolved}: expecting {len(expected)} files matching {allow_patterns}")

    # Keep going while files keep arriving; give up only after MAX_STALLED_ROUNDS
    # rounds in a row with no progress. snapshot_download swallows HTTP 429 (it
    # falls back to "Returning existing local_dir"), so a round with no progress
    # is treated as a rate limit and waits out the 5-minute window.
    stalled, previous, attempt = 0, None, 0
    while True:
        attempt += 1
        missing = [name for name in expected if not (local_dir / name).is_file()]
        if not missing:
            print(f"  all {len(expected)} files present")
            return resolved, expected
        if previous is not None:
            stalled = stalled + 1 if len(missing) >= previous else 0
            if stalled > max(attempts, MAX_STALLED_ROUNDS):
                break
            if stalled:
                print(f"  no progress (likely Hugging Face rate limit); waiting {RATE_LIMIT_WAIT_S:.0f}s")
                time.sleep(RATE_LIMIT_WAIT_S)
            else:
                time.sleep(3.0)
        previous = len(missing)
        print(f"  round {attempt}: {len(missing)} of {len(expected)} files missing")
        try:
            snapshot_download(
                repo_id=repo_id,
                repo_type="dataset",
                revision=resolved,
                local_dir=str(local_dir),
                allow_patterns=allow_patterns,
                token=token,
                max_workers=4,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  ! transfer error ({type(exc).__name__}: {str(exc)[:160]})")

    still_missing = [name for name in expected if not (local_dir / name).is_file()]
    raise RuntimeError(
        f"{repo_id}: {len(still_missing)} of {len(expected)} files are still missing after "
        f"{attempt} rounds (first: {still_missing[0]}). Refusing to continue with a partial "
        "dataset -- the label balance would be silently wrong. Re-run when the network is stable."
    )


def list_repo_dir(repo_id: str, path: str, token: str | None) -> list[dict]:
    """List one directory of a dataset repo (non-recursive)."""
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    entries = retry(
        lambda: list(api.list_repo_tree(repo_id, path_in_repo=path, repo_type="dataset")),
        what=f"{repo_id}:{path} tree",
    )
    return [
        {"path": e.path, "type": "directory" if e.__class__.__name__ == "RepoFolder" else "file"}
        for e in entries
    ]


def download_files(
    repo_id: str,
    *,
    files: list[str],
    local_dir: Path,
    token: str | None,
    revision: str,
    attempts: int = 8,
) -> None:
    """Download an explicit file list and verify every one arrived.

    Used when we want a small selected subset of a large repo: passing exact
    paths as allow_patterns keeps the parallel transfer of snapshot_download
    without pulling the whole tree. Same completeness guarantee as
    ``download_snapshot`` -- a partial result is never accepted silently.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from huggingface_hub import hf_hub_download

    # Deliberately NOT snapshot_download: passing a long explicit allow_patterns
    # list (~1000 entries) trips an internal "min() iterable argument is empty"
    # error in huggingface_hub. Per-file hf_hub_download is reliable, and a small
    # thread pool keeps it fast enough.
    local_dir = Path(local_dir)

    def fetch(name: str) -> tuple[str, str | None]:
        try:
            hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                filename=name,
                revision=revision,
                local_dir=str(local_dir),
                token=token,
            )
            return name, None
        except Exception as exc:  # noqa: BLE001
            return name, f"{type(exc).__name__}: {str(exc)[:120]}"

    stalled, attempt = 0, 0
    while True:
        attempt += 1
        missing = [name for name in files if not (local_dir / name).is_file()]
        if not missing:
            print(f"  all {len(files)} files present")
            return
        print(f"  round {attempt}: fetching {len(missing)} of {len(files)} files")
        errors: list[str] = []
        done = 0
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(fetch, name) for name in missing]
            for future in as_completed(futures):
                _, error = future.result()
                done += 1
                if error:
                    errors.append(error)
                if done % 100 == 0 or done == len(missing):
                    print(f"    {done}/{len(missing)} ({len(errors)} errors)")
        if not errors:
            continue
        print(f"  ! {len(errors)} transfer errors, first: {errors[0]}")
        progressed = len(errors) < len(missing)
        stalled = 0 if progressed else stalled + 1
        if stalled > max(attempts, MAX_STALLED_ROUNDS):
            break
        if any(is_rate_limited(e) for e in errors):
            print(f"  Hugging Face rate limit hit; waiting {RATE_LIMIT_WAIT_S:.0f}s for the window to reset")
            time.sleep(RATE_LIMIT_WAIT_S)
        else:
            time.sleep(min(30.0, 2.0 * (stalled + 1)))

    still = [name for name in files if not (local_dir / name).is_file()]
    raise RuntimeError(
        f"{repo_id}: {len(still)} of {len(files)} files still missing after {attempt} rounds "
        f"(first: {still[0]}). Refusing to continue with a partial download."
    )


def to_mono_16k(wav: np.ndarray, source_rate: int) -> np.ndarray:
    array = np.asarray(wav, dtype=np.float32)
    if array.ndim > 1:
        array = array.mean(axis=1)
    array = np.ascontiguousarray(array, dtype=np.float32)
    if source_rate != TARGET_SAMPLE_RATE:
        array = soxr.resample(array, source_rate, TARGET_SAMPLE_RATE, quality="VHQ")
    return np.ascontiguousarray(array, dtype=np.float32)


@dataclass
class ClipWriter:
    """Writes normalised clips under data/audio/<source>/ and collects rows.

    Clips are stored as 16-bit PCM WAV at 16 kHz mono. 16-bit is not a quality
    compromise here: every source we use is already 16-bit PCM or lossless FLAC
    derived from it, and the model consumes float32 in [-1, 1] either way.
    """

    source_dataset: str
    license_or_consent: str
    output_root: Path
    min_duration_s: float = 1.0
    max_duration_s: float = 30.0
    rows: list[dict[str, object]] = field(default_factory=list)
    skipped_short: int = 0
    skipped_error: int = 0

    def __post_init__(self) -> None:
        self.output_root = Path(self.output_root).resolve()
        self.audio_root = self.output_root / "audio" / safe_name(self.source_dataset)
        self.audio_root.mkdir(parents=True, exist_ok=True)

    def add(
        self,
        wav: np.ndarray,
        source_rate: int,
        *,
        stem: str,
        label: str,
        speaker_id: str,
        language: str,
        attack_family: str = "none",
        generator: str = "none",
        codec: str = "source",
        noise_condition: str = "source",
        subdir: str | None = None,
    ) -> bool:
        if label not in {"bonafide", "spoof"}:
            raise ValueError(f"label must be bonafide or spoof, got {label!r}")
        audio = to_mono_16k(wav, source_rate)
        duration = len(audio) / TARGET_SAMPLE_RATE
        if duration < self.min_duration_s:
            self.skipped_short += 1
            return False
        if duration > self.max_duration_s:
            audio = audio[: int(self.max_duration_s * TARGET_SAMPLE_RATE)]
            duration = len(audio) / TARGET_SAMPLE_RATE

        folder = self.audio_root / (subdir or label)
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / f"{safe_name(stem)}.wav"
        sf.write(destination, audio, TARGET_SAMPLE_RATE, subtype="PCM_16")

        self.rows.append({
            "clip_path": str(destination.relative_to(self.output_root)),
            "label": label,
            "attack_family": attack_family,
            "generator": generator,
            "language": normalise_language(language),
            "speaker_id": f"{self.source_dataset}:{safe_name(speaker_id)}",
            "codec": codec,
            "noise_condition": noise_condition,
            "source_dataset": self.source_dataset,
            "license_or_consent": self.license_or_consent,
            "duration_s": round(float(duration), 3),
        })
        return True

    def add_file(self, path: str | Path, **kwargs) -> bool:
        try:
            wav, rate = sf.read(str(path), dtype="float32", always_2d=False)
        except Exception as exc:  # noqa: BLE001 - report and continue over a large corpus
            print(f"  ! skipping unreadable {path}: {exc}")
            self.skipped_error += 1
            return False
        return self.add(wav, int(rate), **kwargs)

    def summary(self) -> str:
        if not self.rows:
            return "0 clips"
        labels: dict[str, int] = {}
        languages: dict[str, int] = {}
        generators: dict[str, int] = {}
        total = 0.0
        for row in self.rows:
            labels[str(row["label"])] = labels.get(str(row["label"]), 0) + 1
            languages[str(row["language"])] = languages.get(str(row["language"]), 0) + 1
            generators[str(row["generator"])] = generators.get(str(row["generator"]), 0) + 1
            total += float(row["duration_s"])
        return (
            f"{len(self.rows)} clips, {total / 3600.0:.2f} h\n"
            f"    labels:     {dict(sorted(labels.items()))}\n"
            f"    languages:  {dict(sorted(languages.items()))}\n"
            f"    generators: {dict(sorted(generators.items()))}\n"
            f"    skipped:    {self.skipped_short} too short, {self.skipped_error} unreadable"
        )

    def write_candidate(self, provenance: dict[str, object], name: str | None = None) -> Path:
        if not self.rows:
            raise RuntimeError(
                f"{self.source_dataset}: no clips were collected, refusing to write an empty "
                "candidate CSV. Check the source path/filters above."
            )
        candidate_dir = self.output_root / "candidates"
        candidate_dir.mkdir(parents=True, exist_ok=True)
        path = candidate_dir / f"{safe_name(name or self.source_dataset)}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CANDIDATE_COLUMNS)
            writer.writeheader()
            writer.writerows(self.rows)
        sidecar = path.with_suffix(".source.json")
        sidecar.write_text(
            json.dumps(
                {
                    "source_dataset": self.source_dataset,
                    "license_or_consent": self.license_or_consent,
                    "clips": len(self.rows),
                    **provenance,
                },
                indent=2,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"  wrote {path}")
        print(f"  wrote {sidecar}")
        return path
