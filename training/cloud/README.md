# Training on a cloud GPU (Colab or SageMaker)

**You do not copy any files or data by hand.** The cloud machine gets everything itself:

| What | How it gets there |
|---|---|
| Code | `git clone` of this repository |
| Datasets (garystafford, In-the-Wild, IndicVoices, MLAAD, vocoded Indic) | `scripts/prepare_data.sh` downloads them from Hugging Face on the GPU machine |
| AASIST-L pretrained weights | cloned from the official [clovaai/aasist](https://github.com/clovaai/aasist) repo at a pinned commit |
| XLS-R 300M weights | downloaded from Hugging Face (`facebook/wav2vec2-xls-r-300m`) on first use |
| Your Hugging Face token | a Colab secret, or AWS Secrets Manager. **Never** a file in the repo |

Your laptop's `training/data/`, `training/.env` and `backend/.env` stay on your laptop. They are gitignored and the cloud doesn't need them.

---

## 0. One-time setup (both platforms)

1. **Push the code to GitHub.** Colab and SageMaker clone from GitHub, so they only see what has been pushed. The notebook defaults to the public repo [`Hashim-Bhagad/voiceguard`](https://github.com/Hashim-Bhagad/voiceguard) on `main`. If you train from a private fork, add a `GITHUB_TOKEN` Colab secret (a token with read access to it) and change `REPO_URL`.
2. **Accept the gated terms.** Sign in to Hugging Face and accept the gated-access terms of [ai4bharat/IndicVoices](https://huggingface.co/datasets/ai4bharat/IndicVoices), of [ai4bharat/IndicF5](https://huggingface.co/ai4bharat/IndicF5) (the voice-cloning model for Indian languages), and, if you use MLAAD (step 4), of [mueller91/MLAAD](https://huggingface.co/datasets/mueller91/MLAAD). All approve instantly.
3. **Create a read token** at <https://huggingface.co/settings/tokens> (type *Read*). It starts with `hf_`.
4. **Decide on MLAAD.** MLAAD is the only source here with real Indic-language deepfakes (9 Hindi TTS systems), so it matters for accuracy. It is licensed CC-BY-NC-4.0: fine for coursework and research, not for a commercial product. It is on by default in the notebook; switch it off if that licence doesn't fit you.

### Which model?

| | `xlsr_aasist` (default) | `aasist_l` |
|---|---|---|
| What | XLS-R 300M (pre-trained on 128 languages) + AASIST graph head | 85K-parameter raw-waveform model |
| Fine-tuned | top 8 of 24 transformer layers + head (~100M trainable params) | all 85,306 params |
| Strength | accuracy, unseen generators, Indic languages | tiny, runs on a phone or CPU |
| Size | ~1.2 GB ONNX | 0.8 MB ONNX |

Both use the same data, splits and ONNX contract, so their test numbers are directly comparable. Train XLS-R first; train AASIST-L afterwards if you want an on-device model.

---

## Option A: Google Colab (easiest)

1. **Open the notebook in Colab**, then *File → Save a copy in Drive* so your settings persist:
   `https://colab.research.google.com/github/Hashim-Bhagad/voiceguard/blob/main/training/cloud/VoiceGuard_GPU_Training.ipynb`
2. **Choose a GPU:** `Runtime → Change runtime type → GPU`. A T4 works. An L4 or A100 (Colab Pro) is several times faster and supports bf16.
3. **Add the token:** click the key icon in the left sidebar, then *Add new secret*, name it `HF_TOKEN`, paste the token, and switch on *Notebook access*.
4. **Fill in the Settings cell:**
   - `MODEL`: `xlsr_aasist` or `aasist_l`
   - `REPO_URL` / `BRANCH`: leave as they are unless you train from your own fork or branch
   - `ACCEPT_MLAAD_NONCOMMERCIAL`: see step 0.4
   - `MAKE_CLONES` / `CLONES_PER_LANG`: zero-shot voice clones of the bona-fide speakers, made once and cached in Drive. 200 per language takes about 1 hour on a T4.
   - `ACCEPT_XTTS_NONCOMMERCIAL`: XTTS-v2 (the English/Hindi cloner) is under the Coqui Public Model License, which is non-commercial. Without it, only IndicF5 clones are made.
   - `MAX_HOURS`: stop a little before your session limit (free Colab is capped and can disconnect earlier)
5. **Run everything:** `Runtime → Run all`. Approve the Google Drive prompt.

What happens:

| Cell | First run | Later runs |
|---|---|---|
| Code + deps | clone, `pip install -r requirements-gpu.txt` (torch is preinstalled) | `git pull` |
| Data | downloads and preprocesses all sources (~30-60 min, mostly the ~7 GB In-the-Wild archive), generates voice clones (~1 h), then saves a ~3-4 GB tarball to `MyDrive/voiceguard/` | restores the tarball in a few minutes; re-saves it if a new source (such as clones) was added |
| Train | starts from pretrained weights; writes `last.pt` and `best.pt` to Drive every epoch | **resumes** from `last.pt` |
| Evaluate / export | overall test EER, strict EER on unseen generators, clones of unseen speakers, ONNX export, fine-tune report, figures | |

**If Colab disconnects**, reconnect and *Run all* again. Data comes back from Drive and training continues from the last finished epoch.

**Drive space:** keep ~10 GB free for `xlsr_aasist` (two ~1.3 GB checkpoints, a ~1.2 GB ONNX file, and the data tarball). `aasist_l` needs ~4 GB, almost all of it data.

**Results** end up in `MyDrive/voiceguard/outputs/<model>/`: `best.pt`, the `.onnx` export, `metrics_test.json`, `scores_test.csv`, `finetune_report.md` and `figures/`.

---

## Option B: SageMaker training job (recommended for long runs)

A training job runs to completion with no browser open. Managed spot capacity cuts the price substantially, and checkpoints sync to S3 so an interruption resumes instead of restarting.

### B.1 One-time AWS setup

1. **GPU quota.** New accounts often have a quota of **0** for GPU training instances. In *Service Quotas → Amazon SageMaker*, request at least 1 for `ml.g5.2xlarge for training job usage`, and for `ml.g5.2xlarge for spot training job usage` if you want spot. Approval can take a day, so do this first.
2. **Execution role.** Use a SageMaker execution role (Studio creates one) with `AmazonSageMakerFullAccess`, S3 access to the SageMaker default bucket, and `secretsmanager:GetSecretValue` on the secret below.
3. **Store the Hugging Face token** once:
   ```bash
   aws secretsmanager create-secret --name voiceguard/hf-token --secret-string hf_xxxxxxxx
   ```

### B.2 Launch

Run from your laptop (with AWS credentials configured) or from a SageMaker Studio terminal:

```bash
git clone https://github.com/Hashim-Bhagad/voiceguard
cd voiceguard/training
pip install "sagemaker>=2.200,<3"

python cloud/launch_sagemaker.py \
    --role arn:aws:iam::<ACCOUNT_ID>:role/<SageMakerExecutionRole> \
    --hf-token-secret-id voiceguard/hf-token \
    --model xlsr_aasist \
    --accept-mlaad-noncommercial \
    --spot
```

`--role` can be omitted inside SageMaker Studio. Useful flags:

| Flag | Default | Notes |
|---|---|---|
| `--model` | `xlsr_aasist` | or `aasist_l` |
| `--instance-type` | `ml.g5.2xlarge` (A10G 24 GB, 8 vCPU) | `ml.g6.2xlarge` (L4), `ml.g4dn.2xlarge` (T4, cheapest) |
| `--spot` | off | much cheaper; interruptions resume from S3 checkpoints |
| `--epochs` | from config | 12 for XLS-R, 30 for AASIST-L |
| `--itw-max-per-label` | 6000 | In-the-Wild clips per label; `0` = all ~31.8k |
| `--checkpoint-prefix` | new | pass an earlier job's prefix to resume it |
| `--no-wait` | off | submit and return instead of streaming logs |

Only the code is uploaded (about 300 KB). The job then:

1. downloads all datasets (`scripts/prepare_data.sh`);
2. fine-tunes, checkpointing to `s3://<bucket>/voiceguard/checkpoints/<job>/`;
3. evaluates on the held-out test split, exports ONNX, and writes the fine-tune report and figures;
4. packs everything into `s3://<bucket>/voiceguard/<job>/output/model.tar.gz`.

### B.3 Watch and collect

* Logs stream in the terminal. They are also under *SageMaker → Training jobs → (job) → View logs*.
* When the job finishes:
  ```bash
  aws s3 cp s3://<bucket>/voiceguard/<job>/output/model.tar.gz . && tar -xzf model.tar.gz
  ```

### Option B-lite: SageMaker Studio as a plain GPU box

If you would rather drive it by hand, open a JupyterLab space on a GPU instance (for example `ml.g5.2xlarge`), open a terminal, and run the same commands the notebook runs:

```bash
git clone https://github.com/Hashim-Bhagad/voiceguard && cd voiceguard/training
pip install -r requirements-gpu.txt
export HF_TOKEN=hf_xxxxxxxx ACCEPT_MLAAD_NONCOMMERCIAL=1
bash scripts/prepare_data.sh
nohup python train_aasist_l.py --config configs/xlsr_aasist_gpu.yaml > train.log 2>&1 &
tail -f train.log
```

Studio bills while the space is running, even when idle. Stop it when training ends.

---

## After training: plugging the model into the app

Both models produce the same ONNX contract (`waveform float32[batch, 64600]` in, `spoof_logit float32[batch]` out), so the backend needs no code change:

1. Copy the `.onnx` file into `backend/models/`.
2. In `backend/.env`, set `MODEL_BACKEND=aasist-l-onnx` and `AASIST_L_ONNX=models/<file>.onnx`.
3. Restart the backend and check `GET /api/v1/health`: `inference_path` should be `aasist-l-onnx`, with the file's SHA-256.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `could not read Username for 'https://github.com'` | `REPO_URL` points at a private repo: add a `GITHUB_TOKEN` Colab secret, or use the public repo |
| `GatedRepoError` / 401 / 403 on IndicVoices, MLAAD or IndicF5 | Accept the terms with the **same** account that owns the token; check the Colab secret has notebook access |
| Clone step fails, or you want to skip it | Set `MAKE_CLONES = False` (or `CLONE_ENGINES=xtts` / `indicf5` to use one engine). Training works without clones, and the step is skipped once `data/candidates/clones.csv` exists |
| `Requested holdout generator 'veena' is not present` | MLAAD's directory names changed upstream. The error lists the available generators; set `MLAAD_DEV_GENERATORS` / `MLAAD_TEST_GENERATORS` to two of them |
| `ResourceLimitExceeded` on SageMaker | GPU quota is 0; see B.1 step 1 |
| CUDA out of memory | Lower `data.batch_size` in the config and raise `train.grad_accum_steps` by the same factor |
| GPU utilisation is low | Data loading is the bottleneck. Use an instance with more vCPUs and raise `data.num_workers` |
