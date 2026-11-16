"""Launch the full VoiceGuard training pipeline as a SageMaker training job.

Run from your laptop (with AWS credentials) or from SageMaker Studio:

  pip install "sagemaker>=2.200,<3"
  python cloud/launch_sagemaker.py \
      --role arn:aws:iam::<account>:role/<SageMakerExecutionRole> \
      --hf-token-secret-id voiceguard/hf-token \
      --accept-mlaad-noncommercial --spot

What gets uploaded is only the code (src/, scripts/, configs/, cloud/, *.py),
about 300 KB. The job downloads every dataset from Hugging Face itself, trains on
one GPU, and writes best.pt, the ONNX export, metrics and figures to
s3://<bucket>/voiceguard/<job-name>/output/model.tar.gz.

Store the Hugging Face token once in Secrets Manager rather than passing it in
plain text (the execution role needs secretsmanager:GetSecretValue on it):

  aws secretsmanager create-secret --name voiceguard/hf-token --secret-string hf_xxx
"""
from __future__ import annotations

import argparse
import shutil
import tempfile
import time
from pathlib import Path

TRAINING = Path(__file__).resolve().parents[1]
CODE_DIRS = ("src", "scripts", "configs", "cloud")
CODE_FILES = ("train_aasist_l.py", "eval.py", "export_onnx.py")


def stage_code(destination: Path) -> Path:
    """Copy only source files. training/ also holds data, weights and a venv
    (gigabytes) that must not be tarred up and sent to S3."""
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".env", "*.ipynb")
    for name in CODE_DIRS:
        shutil.copytree(TRAINING / name, destination / name, ignore=ignore)
    for name in CODE_FILES:
        shutil.copy2(TRAINING / name, destination / name)
    # The PyTorch container pip-installs requirements.txt from source_dir.
    shutil.copy2(TRAINING / "requirements-gpu.txt", destination / "requirements.txt")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--role", default=None, help="SageMaker execution role ARN (auto-detected in Studio)")
    parser.add_argument("--bucket", default=None, help="S3 bucket (default: the SageMaker default bucket)")
    parser.add_argument("--model", choices=("xlsr_aasist", "aasist_l"), default="xlsr_aasist",
                        help="xlsr_aasist: XLS-R 300M + AASIST head (accuracy); aasist_l: 85K-param edge model")
    parser.add_argument("--instance-type", default="ml.g5.2xlarge",
                        help="ml.g5.2xlarge (A10G 24 GB, 8 vCPU) | ml.g6.2xlarge (L4) | ml.g4dn.2xlarge (T4, cheapest)")
    parser.add_argument("--hf-token-secret-id", default=None, help="Secrets Manager id holding the HF token")
    parser.add_argument("--accept-mlaad-noncommercial", action="store_true",
                        help="Include MLAAD Indic TTS spoof (CC-BY-NC-4.0)")
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--max-run-hours", type=float, default=24.0)
    parser.add_argument("--spot", action="store_true", help="Managed spot training (~60-70%% cheaper, resumable)")
    parser.add_argument("--itw-max-per-label", default="6000", help="In-the-Wild cap per label; 0 = all")
    parser.add_argument("--framework-version", default="2.5")
    parser.add_argument("--py-version", default="py311")
    parser.add_argument("--checkpoint-prefix", default=None,
                        help="Reuse an earlier job's checkpoint prefix to resume it")
    parser.add_argument("--no-wait", action="store_true", help="Return after submitting the job")
    args = parser.parse_args()

    import sagemaker
    from sagemaker.pytorch import PyTorch

    session = sagemaker.Session()
    role = args.role or sagemaker.get_execution_role()
    bucket = args.bucket or session.default_bucket()
    job_name = f"voiceguard-{args.model.replace('_', '-')}-{time.strftime('%Y%m%d-%H%M%S')}"
    checkpoint_prefix = args.checkpoint_prefix or f"voiceguard/checkpoints/{job_name}"

    environment = {
        "ITW_MAX_PER_LABEL": str(args.itw_max_per_label),
        "ACCEPT_MLAAD_NONCOMMERCIAL": "1" if args.accept_mlaad_noncommercial else "0",
        "HF_HOME": "/tmp/hf",  # on the job's EBS volume, not the small root disk
        # 8 vCPU instances can feed the GPU with more loader workers.
        "OMP_NUM_THREADS": "1",
    }
    if args.hf_token_secret_id:
        environment["HF_TOKEN_SECRET_ID"] = args.hf_token_secret_id

    config = {"xlsr_aasist": "configs/xlsr_aasist_gpu.yaml", "aasist_l": "configs/aasist_l_gpu.yaml"}[args.model]
    hyperparameters = {"config": config}
    if args.epochs:
        hyperparameters["epochs"] = args.epochs

    max_run = int(args.max_run_hours * 3600)
    with tempfile.TemporaryDirectory(prefix="voiceguard-src-") as staging:
        source_dir = stage_code(Path(staging))
        estimator = PyTorch(
            entry_point="cloud/sagemaker_entry.py",
            source_dir=str(source_dir),
            role=role,
            framework_version=args.framework_version,
            py_version=args.py_version,
            instance_type=args.instance_type,
            instance_count=1,
            volume_size=200,  # GB: In-the-Wild alone is a ~7 GB archive
            max_run=max_run,
            use_spot_instances=args.spot,
            max_wait=max_run * 2 if args.spot else None,
            checkpoint_s3_uri=f"s3://{bucket}/{checkpoint_prefix}",
            checkpoint_local_path="/opt/ml/checkpoints",
            output_path=f"s3://{bucket}/voiceguard",
            hyperparameters=hyperparameters,
            environment=environment,
            sagemaker_session=session,
            base_job_name=f"voiceguard-{args.model.replace('_', '-')}",
        )
        estimator.fit(job_name=job_name, wait=not args.no_wait)

    print(f"\njob:         {job_name}")
    print(f"checkpoints: s3://{bucket}/{checkpoint_prefix}  (pass --checkpoint-prefix to resume)")
    print(f"artifacts:   s3://{bucket}/voiceguard/{job_name}/output/model.tar.gz")


if __name__ == "__main__":
    main()
