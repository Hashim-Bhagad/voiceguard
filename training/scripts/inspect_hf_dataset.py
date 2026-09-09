"""Inspect Hugging Face dataset configs/features before streaming a capped subset."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from huggingface_hub import HfApi


def load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--revision", default="main")
    args = parser.parse_args()
    load_local_env()
    info = HfApi(token=os.getenv("HF_TOKEN")).dataset_info(args.repo_id, revision=args.revision)
    print(f"repo={args.repo_id}\nresolved_revision={info.sha}")
    if info.card_data:
        print("configs:", info.card_data.get("configs", "not published in card metadata"))
    print("siblings:")
    for sibling in info.siblings[:50]:
        print(" ", sibling.rfilename)
    if len(info.siblings) > 50:
        print(f" ... and {len(info.siblings) - 50} more")


if __name__ == "__main__":
    main()
