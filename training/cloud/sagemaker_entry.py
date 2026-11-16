"""SageMaker training-job entry point: data -> fine-tune -> evaluate -> export.

Launched by cloud/launch_sagemaker.py; you do not run this by hand. Inside the
job the code lives in /opt/ml/code, which is this training/ directory.

  * Checkpoints go to /opt/ml/checkpoints, which SageMaker syncs to S3. A spot
    interruption or a re-launch with the same checkpoint URI resumes from last.pt.
  * Everything a person needs afterwards (best.pt, the ONNX export, metrics,
    figures, the fine-tuning report) is copied to /opt/ml/model, which SageMaker
    uploads as model.tar.gz when the job ends.
  * The Hugging Face token comes from AWS Secrets Manager (HF_TOKEN_SECRET_ID) so
    it never appears in the job definition. A plain HF_TOKEN env var also works.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]
CHECKPOINTS = Path("/opt/ml/checkpoints")
MODEL_DIR = Path(os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))


def run(*cmd: str) -> None:
    print("\n$ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=CODE, check=True)


def load_hf_token() -> None:
    if os.environ.get("HF_TOKEN"):
        return
    secret_id = os.environ.get("HF_TOKEN_SECRET_ID")
    if not secret_id:
        raise SystemExit("Set HF_TOKEN_SECRET_ID (preferred) or HF_TOKEN for the IndicVoices download.")
    import boto3  # present in every SageMaker framework container

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    value = boto3.client("secretsmanager", region_name=region).get_secret_value(SecretId=secret_id)
    secret = value.get("SecretString", "")
    try:  # accept either a bare token or {"HF_TOKEN": "..."}
        secret = json.loads(secret).get("HF_TOKEN", secret)
    except (json.JSONDecodeError, AttributeError):
        pass
    os.environ["HF_TOKEN"] = secret.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    # SageMaker passes hyperparameters as --key value
    parser.add_argument("--config", default="configs/xlsr_aasist_gpu.yaml")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--max-hours", type=float, default=None)
    args, _ = parser.parse_known_args()

    import yaml  # installed from requirements.txt

    load_hf_token()
    cfg = yaml.safe_load((CODE / args.config).read_text())
    run_dir = CODE / cfg["train"]["out_dir"]
    is_aasist_l = str(cfg["model"].get("type", "aasist_l")) == "aasist_l"
    onnx_name = "aasist-l-indic-v0.2.onnx" if is_aasist_l else "xlsr-aasist-indic-v0.1.onnx"
    os.environ.setdefault("PYTHON", sys.executable)  # prepare_data.sh uses the same interpreter

    # Point the run directory at the S3-synced checkpoint dir when it exists.
    if CHECKPOINTS.is_dir():
        run_dir.parent.mkdir(parents=True, exist_ok=True)
        if run_dir.exists() and not run_dir.is_symlink():
            shutil.rmtree(run_dir)
        if not run_dir.exists():
            run_dir.symlink_to(CHECKPOINTS, target_is_directory=True)

    run("bash", "scripts/prepare_data.sh")

    train = [sys.executable, "train_aasist_l.py", "--config", args.config]
    if (run_dir / "last.pt").is_file():
        print("found last.pt in the checkpoint dir: resuming", flush=True)
        train.append("--resume")
    elif is_aasist_l:
        train += ["--pretrained", "weights/AASIST-L.pth"]  # XLS-R initialises itself
    if args.epochs:
        train += ["--epochs", str(args.epochs)]
    if args.max_hours:
        train += ["--max-hours", str(args.max_hours)]
    run(*train)

    best = str(run_dir / "best.pt")
    run(sys.executable, "eval.py", "--ckpt", best, "--save-scores")
    run(sys.executable, "export_onnx.py", "--ckpt", best, "--config", args.config,
        "--out", str(run_dir / onnx_name))
    run(sys.executable, "scripts/inspect_finetune.py", "--config", args.config,
        "--finetuned", best, "--markdown", str(run_dir / "finetune_report.md"),
        "--json", str(run_dir / "finetune_report.json"))
    run(sys.executable, "scripts/plot_results.py", "--run-dir", str(run_dir))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for item in run_dir.iterdir():
        if item.name == "last.pt":
            continue  # resume state only; best.pt is the model
        target = MODEL_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
    shutil.copy2(CODE / "data" / "metadata.csv", MODEL_DIR / "metadata.csv")
    print(f"\nartifacts in {MODEL_DIR}: {sorted(p.name for p in MODEL_DIR.iterdir())}")


if __name__ == "__main__":
    main()
