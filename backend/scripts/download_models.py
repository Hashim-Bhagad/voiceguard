"""Verify that the single Colab-exported AASIST-L model is present locally."""
import argparse
from pathlib import Path

MODEL_NAME = "aasist-l-indic-v0.1.onnx"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL_NAME)
    args = parser.parse_args()
    if args.model != MODEL_NAME:
        raise ValueError(f"VoiceGuard deploys only {MODEL_NAME}")
    destination = Path("models") / MODEL_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        print(f"OK: {destination}")
        return
    print(f"Copy the Colab export to {destination}. See ../training/README.md.")


if __name__ == "__main__":
    main()
