"""Resolve the pretrained AASIST-L checkpoint used to initialise fine-tuning.

The official ClovaAI AASIST repository ships its own trained weights, so once
``scripts/bootstrap_aasist.py`` has cloned the pinned revision the checkpoint is
already on disk at ``third_party/aasist/models/weights/AASIST-L.pth``. This
script copies it to ``weights/`` and -- more importantly -- proves it loads into
the pinned AASIST-L architecture with no missing or unexpected keys.

Prefer this over a third-party Hugging Face mirror: the upstream repo is the
authoritative source and is already pinned to an immutable commit.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))

UPSTREAM_RELATIVE = Path("models/weights/AASIST-L.pth")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_loads(checkpoint: Path, upstream_dir: Path) -> int:
    """Load the checkpoint into the pinned AASIST-L graph. Returns param count."""
    import yaml

    from src.model import build_model

    with open(TRAINING_ROOT / "configs" / "aasist_l.yaml", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    cfg["model"]["upstream_dir"] = str(upstream_dir)
    model = build_model(cfg)
    missing, unexpected = model.load_pretrained(checkpoint)
    if missing or unexpected:
        raise RuntimeError(
            "Checkpoint does not match the pinned AASIST-L architecture "
            f"(missing={len(missing)}, unexpected={len(unexpected)}). "
            "Confirm you are pointing at AASIST-L.pth and not AASIST.pth."
        )
    return sum(p.numel() for p in model.parameters())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--upstream-dir",
        default=str(TRAINING_ROOT / "third_party" / "aasist"),
        help="Pinned clovaai/aasist clone created by scripts/bootstrap_aasist.py",
    )
    parser.add_argument("--output-dir", default=str(TRAINING_ROOT / "weights"))
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip loading the checkpoint into the model (not recommended)",
    )
    args = parser.parse_args()

    upstream_dir = Path(args.upstream_dir).resolve()
    source = upstream_dir / UPSTREAM_RELATIVE
    if not source.is_file():
        raise FileNotFoundError(
            f"{source} is missing. Run 'python scripts/bootstrap_aasist.py' first."
        )

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / source.name
    if destination.resolve() != source.resolve():
        shutil.copy2(source, destination)

    print(f"checkpoint: {destination}")
    print(f"bytes:      {destination.stat().st_size}")
    print(f"sha256:     {sha256(destination)}")
    if args.skip_verify:
        print("verification skipped")
        return
    params = verify_loads(destination, upstream_dir)
    print(f"loaded into pinned AASIST-L: {params} parameters, 0 missing, 0 unexpected")
    print(
        "Note: these weights were trained on ASVspoof 2019 LA (English, older codecs). "
        "Treat them only as an initialisation -- they carry no Indic or modern-TTS claim."
    )


if __name__ == "__main__":
    main()
