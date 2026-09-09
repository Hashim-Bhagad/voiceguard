# Training — AASIST-L only

VoiceGuard uses one acoustic model everywhere: the official [ClovaAI AASIST-L](https://github.com/clovaai/aasist) raw-waveform anti-spoofing model. Fine-tune it on a Colab GPU, export one ONNX file, and run that same model with ONNX Runtime on the FastAPI server, CPU laptop, and phone.

`AASIST-L` is intentionally the only deployable acoustic model. XLS-R, RawNet, WavLM, and ensembles are not part of this pipeline.

## Download this data

Download only data you are licensed and authorised to use. Keep a data-provenance record and consent for every voice used to generate a clone.

| Purpose | Download / generate | Split use |
|---|---|---|
| Primary Indic bona-fide training | [AI4Bharat IndicVoices](https://huggingface.co/datasets/ai4bharat/IndicVoices) | Train; speaker-disjoint from every other split |
| Higher-quality bona-fide holdout | [IndicVoices-R](https://huggingface.co/datasets/ai4bharat/indicvoices_r) | Dev/test bona-fide, subject to licence |
| Hindi accent holdout | [Lahaja](https://huggingface.co/datasets/ai4bharat/Lahaja) | Dev/test Hindi bona-fide |
| Indian-English accent holdout | [Svarah](https://github.com/AI4Bharat/Svarah) | Dev/test Indian-English bona-fide |
| Anti-spoof initial weights / benchmark | [ASVspoof 2019 LA](https://www.asvspoof.org/) and the AASIST-L checkpoint | Use the checkpoint to initialise; do not claim Indic performance from it |
| Primary Indic spoof | Generate consented samples with [IndicF5](https://huggingface.co/ai4bharat/IndicF5) | Train only for generator A |
| Unseen-generator spoof | A second permitted TTS family and a VC system | Dev/test only; each must be unseen in training |
| Generalisation evaluation | [Gary Stafford deepfake-audio-detection](https://huggingface.co/datasets/garystafford/deepfake-audio-detection) and [In-the-Wild](https://www.kaggle.com/datasets/awsaf49/in-the-wild-audio-deepfake-dataset) | Report separately; do not mix into the Indic final test |

For the first credible run, use Hindi, Indian English, Marathi, and Tamil. Build a balanced initial corpus of roughly 3,000–5,000 clips: 2,000–3,000 bona-fide clips plus TTS, VC, replay, and partial-insert spoof clips. Do **not** label an Indian genuine dataset as spoof.

### Required split discipline

`data/metadata.csv` must have:

```csv
clip_path,label,attack_family,generator,language,speaker_id,split,codec,noise_condition,consent_or_license
train/bonafide/hi_0001.wav,bonafide,none,none,hi,speaker_0001,train,clean,quiet,licensed
train/spoof/hi_0002.wav,spoof,tts,indicf5,hi,source_speaker_001,train,clean,quiet,consented
```

The code rejects a manifest unless:

- Each split has bona-fide and spoof clips.
- Speakers are disjoint across train, dev, and test.
- Dev and test each include at least one spoof generator unseen during training.
- Labels are exactly `bonafide` or `spoof`.

Use `generator=none` for bona-fide speech. Include replay and partial inserts using `attack_family=replay` and `attack_family=partial`.

## Colab run

1. Create a Colab notebook with a **T4 GPU** runtime. Copy this `training/` directory into `/content/voiceguard/training` or clone your project there.
2. Open a terminal/cell in the `training/` directory:

```bash
pip install -q -r requirements-colab.txt
python scripts/bootstrap_aasist.py
python scripts/download_pretrained.py --output-dir weights
```

3. Download approved Hugging Face source datasets. This command saves the resolved dataset revision next to the files; it can be large, so use `--allow-pattern` where the source publishes useful subset paths.

```bash
python scripts/download_hf_dataset.py --repo-id ai4bharat/IndicVoices --output-dir data/sources/IndicVoices
python scripts/download_hf_dataset.py --repo-id ai4bharat/indicvoices_r --output-dir data/sources/IndicVoices-R
```

Prepare your consented/generated audio and create `data/metadata.csv`. Dataset schemas differ, so audio selection and manifest construction remain explicit rather than silently assigning labels.

4. Validate, fine-tune, evaluate, and export:

```bash
python scripts/validate_manifest.py --metadata-csv data/metadata.csv --check-files
python train_aasist_l.py --config configs/aasist_l.yaml --pretrained weights/AASIST-L.pth
python eval.py --ckpt outputs/aasist_l_indic/best.pt --metadata-csv data/metadata.csv --threshold-split dev --eval-split test
python export_onnx.py --ckpt outputs/aasist_l_indic/best.pt --out aasist-l-indic-v0.1.onnx
```

Copy `aasist-l-indic-v0.1.onnx` to `backend/models/`, set `MODEL_BACKEND=aasist-l-onnx`, and restart the backend. The ONNX file accepts `waveform: float32[batch, 64600]` at 16 kHz and returns `spoof_logit: float32[batch]`; positive values mean more spoof-like.

## Files

- `scripts/bootstrap_aasist.py` — clones the official AASIST source at a pinned revision.
- `scripts/download_pretrained.py` — downloads the public upstream-compatible AASIST-L checkpoint.
- `scripts/download_hf_dataset.py` — reproducibly snapshots approved Hugging Face datasets.
- `scripts/validate_manifest.py` — validates labels, paths, speaker splits, and generator holdout.
- `src/model.py` — adapter for only the official AASIST-L architecture.
- `src/dataset.py` — 16 kHz, 64,600-sample windows and label-neutral narrowband/noise/RIR augmentation.
- `train_aasist_l.py` — GPU fine-tuning with mixed precision, cosine decay, gradient clipping, and dev-EER early stopping.
- `eval.py` — dev-thresholded fixed-test EER, ROC-AUC, PR-AUC, and group FPR/FNR.
- `export_onnx.py` — ONNX export plus a PyTorch/ONNX numerical equivalence check.

Do not report an accuracy, latency, quantisation, or phone-compatibility claim until the final exported model has been measured on your held-out Indic test set and actual target devices.


## Local credentials

`training/.env` is loaded automatically by the Hugging Face download scripts and is ignored by Git. It contains `HF_TOKEN` and `KAGGLE_API_TOKEN`; never upload it to a public notebook, commit it, or share it in chat. For Colab, create `HF_TOKEN` and `KAGGLE_API_TOKEN` as private **Colab Secrets** instead. Kaggle downloads may additionally require `KAGGLE_USERNAME`, depending on the Kaggle client/account authentication flow.


## Full Indic run (selected)

The full run uses Hindi (`hi`), Indian English (`en-IN`), Marathi (`mr`), and Tamil (`ta`). **Do not use `download_hf_dataset.py` to mirror IndicVoices or IndicVoices-R:** their published scale makes full snapshots impractical. Instead, inspect their actual current config and feature names, then stream an intentionally capped subset with `scripts/collect_hf_bonafide.py`. The provenance JSON written beside each candidate CSV captures the resolved source revision.

```bash
python scripts/inspect_hf_dataset.py --repo-id ai4bharat/IndicVoices
python scripts/inspect_hf_dataset.py --repo-id ai4bharat/indicvoices_r
# After replacing each <verified-...> value from the inspection result:
python scripts/collect_hf_bonafide.py \
  --repo-id ai4bharat/IndicVoices --config <verified-config> --source-split <verified-split> \
  --source-name indicvoices --target-split train --languages hi en-IN mr ta \
  --max-per-language 400 --audio-field <verified-audio-field> \
  --language-field <verified-language-field> --speaker-field <verified-speaker-field> \
  --license-or-consent "IndicVoices terms accepted" --output-root data
```

Use IndicVoices-R as bona-fide dev/test, Lahaja only as a gated Hindi holdout, and Svarah only as an Indian-English holdout. Generate `indicf5`/VC-A training spoof clips from consented donors; reserve TTS-B/VC-B for dev and TTS-C/VC-C for test where possible. Register every reviewed source in `data/candidates/*.csv`, using `data_templates/full_run_source_candidates.csv` as the column template. Full source budgets, split rules, and assembly instructions are in [`data_templates/full_run_plan.md`](data_templates/full_run_plan.md).

```bash
python scripts/assemble_full_manifest.py --candidates-dir data/candidates --out data/metadata.csv --check-files
python scripts/validate_manifest.py --metadata-csv data/metadata.csv --check-files
```

Both checks must pass before you run `train_aasist_l.py` or the Colab notebook. The source descriptions above were rephrased for compliance with licensing restrictions.
