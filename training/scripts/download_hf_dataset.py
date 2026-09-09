"""Download a Hugging Face dataset snapshot while recording its resolved revision."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download


def load_local_env() -> None:
    """Load training/.env without requiring an additional dotenv dependency."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--allow-pattern", action="append", default=[])
    args = parser.parse_args()

    load_local_env()
    info = HfApi(token=os.getenv("HF_TOKEN")).dataset_info(args.repo_id, revision=args.revision)
    output_dir = Path(args.output_dir)
    snapshot_download(
        repo_id=args.repo_id,
        repo_type="dataset",
        revision=info.sha,
        local_dir=str(output_dir),
        allow_patterns=args.allow_pattern or None,
        token=os.getenv("HF_TOKEN"),
    )
    (output_dir / "voiceguard-source.json").write_text(
        json.dumps({"repo_id": args.repo_id, "revision": info.sha}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Downloaded {args.repo_id}@{info.sha} to {output_dir}")


if __name__ == "__main__":
    main()
