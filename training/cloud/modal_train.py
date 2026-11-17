"""Run the full VoiceGuard GPU pipeline as one Modal job (an alternative to the Colab notebook).

    modal deploy training/cloud/modal_train.py                    # once (and after edits)
    python -c "import modal; modal.Function.from_name('voiceguard-train', 'train').spawn()"
    modal app logs voiceguard-train                               # follow the run

    # or, without deploying (spawns and returns; the run continues on Modal):
    modal run --detach training/cloud/modal_train.py [--model aasist_l]
    modal volume get voiceguard outputs/xlsr_aasist_v2 ./runs/    # fetch results

What it does, in a fresh container with an L4, A10G or T4 GPU (whichever is free first):

1. Clones this repository at ``--branch`` (default main) and installs requirements-gpu.txt.
2. Restores the processed dataset tarball from the ``voiceguard`` Volume. If it is not
   there yet and an rclone config is available (see secrets below), the Colab run's
   ``MyDrive/voiceguard/voiceguard-data.tar`` is copied over first. Otherwise
   prepare_data.sh downloads every source from Hugging Face (30-60 min).
3. Runs scripts/prepare_data.sh: skips finished sources, generates the voice clones
   (XTTS-v2 + IndicF5), rebuilds the manifest. Re-saves the tarball when sources changed.
4. Trains (resuming from ``last.pt`` if the Volume has one), evaluates, exports ONNX,
   writes the fine-tune report and figures. Everything lands in
   ``/vol/outputs/<model>_v2`` on the Volume.

Secrets come from a Modal Secret named "voiceguard-train", created once:
  * HF_TOKEN (IndicVoices, MLAAD and IndicF5 are gated)
  * RCLONE_CONF, optional: an rclone config with a "gdrive" remote, to fetch the Colab tarball

    modal secret create voiceguard-train HF_TOKEN=hf_... RCLONE_CONF="$(cat ~/.config/rclone/rclone.conf)"
"""
from __future__ import annotations

import os
from pathlib import Path

import modal

APP_NAME = "voiceguard-train"
REPO_URL = "https://github.com/Hashim-Bhagad/voiceguard.git"
VOL = Path("/vol")
SECRET_NAME = "voiceguard-train"

app = modal.App(APP_NAME)
volume = modal.Volume.from_name("voiceguard", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "ffmpeg", "curl", "rclone", "libsndfile1")
    # torch/torchaudio 2.8: torchaudio >= 2.9 routes load() through torchcodec, which the
    # IndicF5 / F5-TTS inference code is not ready for.
    .pip_install("torch==2.8.0", "torchaudio==2.8.0", extra_index_url="https://download.pytorch.org/whl/cu128")
    .pip_install_from_requirements(str(Path(__file__).resolve().parents[1] / "requirements-gpu.txt"))
    # Stay on the major versions the code is tested with (Colab and CI): pandas 3 and
    # librosa 1 changed defaults that the data pipeline has not been checked against.
    .pip_install("pandas>=2.1,<3", "librosa>=0.10,<1")
    .env({"PYTHONUNBUFFERED": "1", "HF_HUB_ENABLE_HF_TRANSFER": "0"})
)


def sh(cmd: str, cwd: str | None = None, what: str | None = None) -> None:
    import subprocess
    import sys

    print(f"\n$ {cmd}", flush=True)
    proc = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    while chunk := proc.stdout.read1(4096):
        sys.stdout.write(chunk.decode(errors="replace"))
        sys.stdout.flush()
    if proc.wait():
        raise RuntimeError(f"{what or cmd} failed (exit code {proc.returncode})")


@app.function(
    image=image,
    # First GPU type with free capacity wins: L4 sat in Modal's queue for 45 min once.
    # A10G has the same 24 GB; T4 (16 GB) still fits batch 16 with fp16.
    gpu=["L4", "A10G", "T4"],
    cpu=6,              # data loading + augmentation was the bottleneck on Colab's 2 vCPUs
    memory=24 * 1024,
    timeout=8 * 60 * 60,
    volumes={str(VOL): volume},
    secrets=[modal.Secret.from_name(SECRET_NAME)],
)
def train(model: str = "xlsr_aasist", branch: str = "main", clones_per_lang: int = 200,
          make_clones: bool = True, epochs: int = 0) -> str:
    import shutil
    import subprocess

    import yaml

    repo, training = "/root/vg", "/root/vg/training"
    shutil.rmtree(repo, ignore_errors=True)  # Modal may reuse a warm container from an earlier call
    sh(f"git clone -q --depth 1 --branch {branch} {REPO_URL} {repo}")
    sha = subprocess.check_output(["git", "-C", repo, "rev-parse", "--short", "HEAD"], text=True).strip()
    print(f"code at {branch} @ {sha}", flush=True)
    sh("nvidia-smi --query-gpu=name,memory.total --format=csv")

    os.environ.update(
        ACCEPT_MLAAD_NONCOMMERCIAL="1", ACCEPT_XTTS_NONCOMMERCIAL="1",
        MAKE_CLONES="1" if make_clones else "0", CLONES_PER_LANG=str(clones_per_lang),
        HF_HOME=str(VOL / "hf-cache"),
    )

    # Modal can preempt the GPU at any time and restart this function from the top.
    # Commit the Volume every few minutes so clones and checkpoints made so far survive.
    import threading

    def _committer():
        while True:
            threading.Event().wait(300)
            try:
                volume.commit()
            except Exception as exc:  # noqa: BLE001
                print(f"  (volume commit failed: {exc})", flush=True)

    threading.Thread(target=_committer, daemon=True).start()

    # --- data -------------------------------------------------------------------
    tar = VOL / "voiceguard-data.tar"
    stamp = VOL / "voiceguard-data.tar.sources"
    if not tar.exists() and os.environ.get("RCLONE_CONF"):
        conf = Path.home() / ".config" / "rclone" / "rclone.conf"
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text(os.environ["RCLONE_CONF"])
        print("copying the Colab data tarball from Google Drive ...", flush=True)
        sh(f"rclone copyto gdrive:voiceguard/voiceguard-data.tar {tar}.part && mv {tar}.part {tar}",
           what="copying the tarball from Drive")
        conf.unlink()
        volume.commit()
    if tar.exists():
        sh(f"tar -xf {tar} -C {training}", what="restoring the data tarball")

    # Clone plan + generated clone audio live on the Volume, so a restarted job resumes
    # where it stopped (make_clone_spoof.py reuses the plan and skips finished clips).
    cache = VOL / "clone-cache"
    for local, remote in ((Path(training, "data/clone_plan"), cache / "plan"),
                          (Path(training, "data/audio/clones"), cache / "audio")):
        remote.mkdir(parents=True, exist_ok=True)
        if local.is_symlink():
            local.unlink()
        elif local.exists():
            shutil.copytree(local, remote, dirs_exist_ok=True)
            shutil.rmtree(local)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.symlink_to(remote)

    sh("bash scripts/prepare_data.sh", cwd=training, what="data preparation")

    sources = "\n".join(sorted(f"{p.name} {p.stat().st_size}"
                               for p in Path(training, "data/candidates").glob("*.csv")))
    if not tar.exists() or not stamp.exists() or stamp.read_text() != sources:
        print("saving the processed data to the Volume ...", flush=True)
        sh(f"tar -chf {tar}.part -C {training} data/audio data/candidates data/metadata.csv "
           f"data/metadata.build.json && mv {tar}.part {tar}", what="saving the data tarball")
        stamp.write_text(sources)
        volume.commit()

    # --- train ------------------------------------------------------------------
    config = {"xlsr_aasist": "configs/xlsr_aasist_gpu.yaml", "aasist_l": "configs/aasist_l_gpu.yaml"}[model]
    cfg = yaml.safe_load(open(Path(training, config)))
    cfg["data"]["num_workers"] = 6
    Path(training, config).write_text(yaml.safe_dump(cfg, sort_keys=False))
    out_dir = cfg["train"]["out_dir"]                       # e.g. outputs/xlsr_aasist
    run_vol = VOL / "outputs" / f"{Path(out_dir).name}_v2"
    run_vol.mkdir(parents=True, exist_ok=True)
    run = Path(training, out_dir)
    run.parent.mkdir(parents=True, exist_ok=True)
    if run.exists() and not run.is_symlink():
        shutil.rmtree(run)
    run.symlink_to(run_vol)

    start = "--resume" if (run / "last.pt").exists() else (
        "--pretrained weights/AASIST-L.pth" if model == "aasist_l" else "")
    epochs_arg = f"--epochs {epochs}" if epochs else ""
    try:
        sh(f"python train_aasist_l.py --config {config} {start} {epochs_arg}", cwd=training, what="training")
    finally:
        volume.commit()

    onnx = {"xlsr_aasist": "xlsr-aasist-indic-v0.2.onnx", "aasist_l": "aasist-l-indic-v0.3.onnx"}[model]
    sh(f"python eval.py --ckpt {run}/best.pt --save-scores", cwd=training, what="evaluation")
    volume.commit()
    sh(f"python export_onnx.py --ckpt {run}/best.pt --config {config} --out {run}/{onnx}", cwd=training,
       what="ONNX export")
    sh(f"python scripts/inspect_finetune.py --config {config} --finetuned {run}/best.pt "
       f"--markdown {run}/finetune_report.md --json {run}/finetune_report.json", cwd=training,
       what="fine-tune report")
    sh(f"python scripts/plot_results.py --run-dir {run}", cwd=training, what="plots")
    shutil.copy(Path(training, "data/metadata.build.json"), run_vol / "metadata.build.json")
    Path(run_vol, "code_version.txt").write_text(f"{branch} @ {sha}\n")
    volume.commit()
    return str(run_vol)


@app.local_entrypoint()
def main(model: str = "xlsr_aasist", branch: str = "main", clones_per_lang: int = 200,
         make_clones: bool = True, epochs: int = 0):
    # spawn, not remote: a blocking .remote() call is cancelled if this local client dies
    # (an expired auth token killed a 3-hour run that way), even under --detach.
    call = train.spawn(model=model, branch=branch, clones_per_lang=clones_per_lang,
                       make_clones=make_clones, epochs=epochs)
    print(f"\nstarted {call.object_id}. It runs on Modal without this terminal.")
    print(f"  logs:    modal app logs {APP_NAME}")
    print("  results: modal volume get voiceguard outputs/<model>_v2 ./runs/")
