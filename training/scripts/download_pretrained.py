"""Download the reviewed public AASIST-L checkpoint for fine-tuning."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO_ID = "SpeechAntiSpoofingBenchmarks/AASIST-L"
FILENAME = "AASIST-L.pth"


def load_local_env() -> None:
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
    parser.add_argument("--output-dir", default="weights")
    args = parser.parse_args()
    load_local_env()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = hf_hub_download(
        repo_id=REPO_ID,
        filename=FILENAME,
        local_dir=str(output_dir),
        token=os.getenv("HF_TOKEN"),
    )
    print(downloaded)


if __name__ == "__main__":
    main()
