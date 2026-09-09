"""Clone the official AASIST repository at the reviewed, immutable revision."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

UPSTREAM_URL = "https://github.com/clovaai/aasist.git"
UPSTREAM_REVISION = "a04c9863f63d44471dde8a6abcb3b082b07cd1d1"


def run(*command: str, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", default="third_party/aasist")
    args = parser.parse_args()
    destination = Path(args.destination)
    if destination.exists():
        run("git", "-C", str(destination), "rev-parse", "--verify", "HEAD")
        print(f"AASIST already exists at {destination}; remove it only if you intentionally need a fresh clone.")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    run("git", "clone", UPSTREAM_URL, str(destination))
    run("git", "checkout", "--detach", UPSTREAM_REVISION, cwd=destination)
    print(f"Pinned official AASIST source at {destination} ({UPSTREAM_REVISION})")


if __name__ == "__main__":
    main()
