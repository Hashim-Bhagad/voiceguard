<div align="center">

# VoiceGuard · TRUST & VISHWAS

**Real-time voice-impersonation screening for Indian languages.**
Detects AI-cloned voices, flags social-engineering language, and asks the caller to prove they are live.

![Landing page](docs/images/landing.png)

</div>

---

## Why

A cloned voice now costs a few seconds of audio and a free TTS account. The scams that follow, such as an "urgent transfer" from the CEO or a "KYC update" from the bank, rarely arrive in clean studio English. They come in Hindi, Hinglish, Marathi and Tamil, over a phone line. VoiceGuard scores **how** something is said, **what** is said, and **whether a live human is on the line**, and keeps those signals separate so a reviewer can see why a call was flagged.

## How it works

```mermaid
flowchart LR
    A[Call audio / upload<br/>16 kHz mono] --> B[Voice activity +<br/>quality gate]
    B --> C[Acoustic model<br/>XLS-R + AASIST · or AASIST-L<br/>ONNX Runtime]
    B --> D[Speech-to-text<br/>Groq Whisper]
    D --> E[Linguistic risk<br/>EN · HI · MR · TA · Hinglish lexicons]
    C --> F{Fusion<br/>0.55 acoustic + 0.25 linguistic + 0.20 context<br/>EMA smoothing}
    E --> F
    F -->|low| G[Continue]
    F -->|review| H[Verify]
    F -->|high| I[Hold + liveness challenge<br/>“repeat 4-7-2-9” within 30 s]
    C --> J[Explainability<br/>pitch micro-jitter · 3–4.5 kHz<br/>spectral discontinuity]
```

| Signal | What it measures | Status |
|---|---|---|
| **Acoustic** | Spoof probability from a fine-tuned anti-spoofing network over 4.04 s windows (up to 8 windows per clip, 50% overlap, mean-aggregated) | Trained model |
| **Linguistic** | Urgency, secrecy, authority-impersonation and credential-harvesting cues in the transcript, in 4 languages + Hinglish | Working |
| **Context** | Session-level risk prior | Working |
| **Liveness challenge** | Random 4-digit spoken challenge, 30 s expiry, response latency (clone pipelines lag), transcript match + acoustic re-check | Working |
| **Explainability** | Pitch micro-jitter and spectral discontinuity, reported next to the score | Working |
| Speaker consistency, prosody, VAD | ECAPA embeddings, F0/pause statistics, Silero VAD | Placeholders (roadmap) |

![Analysis view](docs/images/analysis.png)

---

## The model

The acoustic signal comes from a model **fine-tuned in this repo** and served as a single ONNX file with a fixed contract (`waveform float32[batch, 64600]` in, `spoof_logit float32[batch]` out). The backend therefore never changes when the model does. Two models implement that contract:

| | **AASIST-L** (edge) | **XLS-R + AASIST** (accuracy) |
|---|---|---|
| Base | Official [ClovaAI AASIST-L](https://github.com/clovaai/aasist), pre-trained on ASVspoof 2019 LA | [`facebook/wav2vec2-xls-r-300m`](https://huggingface.co/facebook/wav2vec2-xls-r-300m), self-supervised on 436K h in 128 languages |
| Input | raw waveform → sinc-conv filterbank | raw waveform → CNN encoder → 24 transformer layers |
| Fine-tuned | **all 85,306 parameters**: 14 Conv2d, 45 Linear and 18 BatchNorm layers, 4 graph-attention layers | **top 8 of 24 transformer layers** + learned weights over all 25 hidden states + a new AASIST graph back-end (~100M trainable); CNN and layers 0-15 frozen |
| Optimiser | Adam 1e-4, cosine to 5e-6, weight decay 1e-4, grad-clip 5 | Adam: 1e-4 head / 1e-5 encoder, cosine, grad-clip 5 |
| Size | 0.8 MB ONNX | ~1.2 GB ONNX |
| Runs on | phone, laptop CPU | server CPU / GPU |

### Training data and splits

`training/scripts/prepare_data.sh` builds one manifest from five downloaded sources plus two generated ones:

| Source | Contributes | Languages |
|---|---|---|
| [garystafford/deepfake-audio-detection](https://huggingface.co/datasets/garystafford/deepfake-audio-detection) | 933 real + 933 fake from 6 commercial TTS systems (ElevenLabs, Amazon Polly, Speechify, Kokoro, Hume, LuvVoice) | English |
| [In-the-Wild](https://huggingface.co/datasets/mueller91/In-The-Wild) | real-world celebrity speech and deepfakes (37.9 h) | English |
| [IndicVoices](https://huggingface.co/datasets/ai4bharat/IndicVoices) | bona-fide spontaneous speech | Hindi, Marathi, Tamil, Bengali |
| [MLAAD](https://huggingface.co/datasets/mueller91/MLAAD) | deepfakes from 9 Hindi TTS systems (IndicF5, Veena, XTTS v2, Bark…) | Hindi |
| Vocoder re-synthesis of held-out IndicVoices speakers | same-channel Indic spoof (Griffin-Lim, mel-Griffin-Lim, phase reset) | Indic |
| **Zero-shot voice clones** of the bona-fide speakers ([`make_clone_spoof.py`](training/scripts/make_clone_spoof.py)) | 200 clones per language from a few seconds of each speaker's real voice: [XTTS-v2](https://huggingface.co/coqui/XTTS-v2) (English, Hindi) and [IndicF5](https://huggingface.co/ai4bharat/IndicF5) (Hindi, Bengali, Tamil, Marathi) | all five |

The split logic prevents the usual ways an anti-spoofing EER gets inflated:

* **Speaker-disjoint.** No speaker appears in more than one split, so the model can't recognise voices instead of artefacts.
* **Generator holdout.** Entire TTS systems are kept out of training. Dev uses ElevenLabs (+ Veena); test uses Speechify, Kokoro (+ Bark). A held-out generator's clips are never moved into train, even to keep a speaker together; the speaker's other clips move instead.
* **Split by speaker where a generator can't be held out.** In-the-Wild's deepfakes carry no generator labels, and the voice clones are deliberately clones of the bona-fide speakers. Both are split together with their speaker's real clips, so every cloned voice has genuine recordings in the same split. The model can't separate "real" from "clone" by recognising the voice, and test clones are clones of people it never heard. `eval.py` reports these "unseen speaker, seen tool" clips separately from the strict EER on unseen generators.
* **Balanced sampling** by (label × language), so "English" and "spoof" never become correlated within a batch.
* **Label-neutral augmentation.** Every augmentation is applied with equal probability to both classes, so it can't become a feature (see [`src/channel_aug.py`](training/src/channel_aug.py) and [`src/dataset.py`](training/src/dataset.py)):
  * **[RawBoost](https://arxiv.org/abs/2111.04433)** (Tak, Kamble, Patino, Todisco and Evans, ICASSP 2022), on 40% of clips. It adds one of linear/non-linear convolutive noise, impulsive signal-dependent noise, stationary signal-independent noise, or the first two in series. These model device and channel nuisances without needing any noise corpus. The wav2vec 2.0 + AASIST results this model follows were trained with RawBoost. Ours is reimplemented from the paper and the [reference code](https://github.com/TakHemlata/RawBoost-antispoofing) with the paper's default parameters. Two deliberate differences: FFT convolution, so it stays cheap on two CPU cores, and loudness matched back to the input.
  * **Lossy codec round trips**, on 40% of clips. Each clip is encoded and decoded in memory through Opus at WhatsApp/VoIP bitrates (8-32 kbps), MP3, AAC or G.711 μ-law/A-law. This was added after genuine English speech sent through WhatsApp-style compression was flagged as fake 80% of the time in the real-world test.
  * Telephony narrowband round trip, MUSAN-style noise at 5-20 dB SNR, room impulse responses and ±3 dB gain.

### Results so far

Held-out **test** split: 3,733 clips (1,810 genuine, 1,923 spoof) in English, Hindi, Bengali, Marathi and Tamil. Every speaker in it is unseen in training. 378 of the spoofs come from TTS systems **never seen in training** (Speechify, Kokoro, IndicF5); the other 1,545 are In-the-Wild deepfakes of unseen speakers.

| Model | Trained on | Test EER ↓ | ROC-AUC ↑ |
|---|---|---:|---:|
| AASIST-L, original ASVspoof 2019 weights (no fine-tuning) | none | 43.4% | n/a |
| AASIST-L, fine-tuned (laptop CPU, 454-clip English test) | 1,108 English clips | 25.3% | 0.844 |
| **XLS-R 300M + AASIST, top 8 of 24 layers fine-tuned** (Colab T4, 27 min) | 6,646 clips, all 5 sources | **2.97%** | **0.996** |

XLS-R + AASIST on the test split, broken down:

| Slice | Clips | EER | Clones missed (FNR) |
|---|---:|---:|---:|
| English | 3,255 | 3.54% | 0.2% |
| Hindi | 203 | 0.99% | 0.0% |
| Unseen TTS (Speechify, Kokoro, IndicF5) | 378 | n/a | 0.0% |
| In-the-Wild deepfakes | 1,545 | n/a | 0.3% |

* **Run:** 101M of 316M parameters trainable (XLS-R layers 16-23, the layer-weighting head and the AASIST back-end). fp16 mixed precision, balanced (label × language) sampling. Dev EER was best (9.04%) at epoch 5, and training stopped early after epoch 9.
* **Thresholds:** the dev threshold is conservative on test. At that threshold it misses 0.2% of clones but flags 13.8% of genuine clips, almost all of them noisy In-the-Wild recordings (18.1% flagged, against 2.4% on clean sources). The dev split is small (1,185 clips), so recalibrating the threshold on a larger dev set is the next step.
* **In-the-Wild is not a held-out generator.** The manifest builder keeps each speaker in one split. In-the-Wild has real and fake clips of the same celebrities, so when a speaker's real clips landed in train, their fake clips were moved there too. In-the-Wild deepfakes therefore appear in both train and test, with different speakers. The strict generator-holdout result is the unseen-TTS row: 0 of 378 clones missed.
* **Language coverage:** Bengali, Marathi and Tamil only have genuine clips in test (false-positive rate 0%, 4.3% and 1.2%), so the model's behaviour on clones in those languages is not measured yet.

The full corpus and the larger model took the test error from 25.3% to 2.97%. The two numbers come from different test sets, so treat this as a direction rather than an exact ratio.

<p align="center"><img src="docs/images/aasist_l_training_curve.png" width="640" alt="AASIST-L fine-tuning curve"></p>

The first CPU run of AASIST-L, on 1.1k clips: train loss keeps falling, but dev EER is best at epoch 1, a sign the model was memorising its three training TTS systems. That is why the GPU run uses the full corpus and keeps generator holdout strict.

### What "fine-tuned all layers" actually means

`training/scripts/inspect_finetune.py` checks each block of the network: is it trainable, does a real loss produce a usable gradient there, and how far did its weights move from the pretrained checkpoint. For AASIST-L:

| Block group | Params | Receives gradient | Weight change |
|---|---:|---:|---:|
| Residual encoder (6 blocks) | 50,792 | 50,520 | 1.3–1.7% |
| Spectral + temporal GAT | 3,744 | 3,744 | 1.3–1.5% |
| Heterogeneous GAT (4 layers) | 29,664 | 21,728 | 2.6–3.1% |
| Graph pooling, positional, master nodes, first BN | 784 | 784 | 0.2–3.8% |
| Output layer | 322 | 322 | 6.3% |
| **Total** | **85,306** | **77,098 (90.4%)** | |

Two findings came out of this:

1. **The attention weights of all four heterogeneous graph-attention layers never train.** They sit behind a softmax at temperature 100 and a saturated `tanh`, so with the pretrained weights their gradients are ~1e-43, below what Adam can turn into an update. After fine-tuning they are bit-identical to the checkpoint. That's 7,936 parameters, effectively frozen.
2. **Five `BatchNorm` layers are dead code upstream.** `Residual_block.forward` computes `bn1(x)` and then overwrites it with `conv1(x)`, so 272 parameters are never used.

The XLS-R back-end re-implements the residual encoder without that bug, and its tests assert that every trainable parameter receives a gradient.

---

## Quickstart

### Backend (FastAPI + ONNX Runtime)

```bash
cd backend
uv sync --extra dev
cp .env.example .env            # MODEL_BACKEND=aasist-l-onnx to use the committed model
uv run uvicorn app.main:app --reload --port 8000
# http://localhost:8000/docs
uv run pytest
```

The 0.8 MB `backend/models/aasist-l-indic-v0.1.onnx` is committed, so a fresh clone serves the real model. `GET /api/v1/health` reports which inference path is live and the model file's SHA-256, so a heuristic fallback can never pass for the neural model.

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/verify/file` | Score an uploaded recording (all signals + explainability) |
| `WS /ws/stream` | Stream PCM chunks, get live risk updates |
| `POST /api/v1/challenge/create` · `/challenge/verify-audio` | Liveness challenge |
| `GET /api/v1/health` · `/health/model` | Provable model status |
| `GET /api/v1/sessions` · `/alerts` · `/policy` | Session history, alerts, thresholds |

### Frontend (React + Vite)

```bash
cd frontend
npm ci
npm run dev                     # http://localhost:5173; set VITE_API_BASE_URL to reach the backend
```

Four prepared scenarios (Hinglish CEO scam, Hindi KYC fraud, genuine Indian English, synthetic clone) work without a backend.

### Training

| Where | How |
|---|---|
| **Colab / SageMaker GPU** | [`training/cloud/README.md`](training/cloud/README.md): one notebook, or one launcher command. No manual data copying |
| Laptop CPU | [`training/README.md`](training/README.md): measured memory and throughput, resumable runs |

```bash
cd training
bash scripts/prepare_data.sh                                     # all datasets → data/metadata.csv
python train_aasist_l.py --config configs/xlsr_aasist_gpu.yaml   # or aasist_l_gpu.yaml
python eval.py --ckpt outputs/xlsr_aasist/best.pt --save-scores  # EER on unseen generators
python export_onnx.py --ckpt outputs/xlsr_aasist/best.pt --out xlsr-aasist.onnx
python scripts/inspect_finetune.py --config configs/xlsr_aasist_gpu.yaml --finetuned outputs/xlsr_aasist/best.pt
```

---

## Deployment

Live demo: **https://voiceguard-pink.vercel.app** (frontend on Vercel, backend on [Agent37](https://www.agent37.com)).
Model weights (ONNX, CC-BY-NC-4.0): **[Hashim-Bhagad/voiceguard-xlsr-aasist-indic](https://huggingface.co/Hashim-Bhagad/voiceguard-xlsr-aasist-indic)** on Hugging Face, with a model card, evaluation and `inference.py`.

| Part | Where | Notes |
|---|---|---|
| Frontend (React/Vite) | Vercel, project root `frontend/` | Redeploys on every push to `main`. `VITE_API_BASE_URL` points at the backend. |
| Backend (FastAPI + ONNX Runtime) | Agent37, 2 vCPU / 4 GB / 12 GB disk, auto-sleep after 15 min idle | Image from [`backend/Dockerfile.agent37`](backend/Dockerfile.agent37). It serves the full XLS-R + AASIST model (`xlsr-aasist-indic-v0.1`). |

* **Model on disk.** The 1.26 GB model is larger than Agent37's 1 GB build upload, so it sits on the instance's persistent disk at `/root/models/`, outside the image, and survives sleep, restarts and image updates. It was copied there once from the training run's Drive folder.
* **Why the full model.** An int8-quantised export was 3.5x smaller, but on the same 332 clips it scored 5.42% EER against 4.22%, caught 13 of 16 of the team's real voice clones against 16 of 16, and was no faster on CPU.
* **Secrets.** `GROQ_API_KEY` (speech-to-text) and `CORS_ORIGINS` (the Vercel domain only) are instance environment variables, never baked into the image.
* **Cold starts.** Nothing wakes the backend on page load: sample calls never need it. The workspace pings `/api/v1/health` on upload intent (opening the Upload or Record tab, pointing at the drop zone or a record button, dragging a file in), so the model loads while the person picks a file. A cold start takes 10-30 s; after that, a clip takes about 3-9 s including transcription.

## Repository layout

```text
backend/      FastAPI service: scoring, fusion, STT, challenge, explainability, Firestore
frontend/     React 19 + Vite + Motion dashboard and landing page
training/
  src/          dataset (windows, augmentation), AASIST-L adapter, XLS-R + AASIST model
  scripts/      ingest_*, build_manifest, prepare_data.sh, inspect_finetune, plot_results
  configs/      aasist_l.yaml (CPU), aasist_l_gpu.yaml, xlsr_aasist_gpu.yaml
  cloud/        Colab notebook, SageMaker launcher + entry point, step-by-step guide
  train_aasist_l.py · eval.py · export_onnx.py
docs/images/  README figures
```

## Limits worth knowing

* A risk score is **not proof of identity**. The UI says so, and the challenge step exists for that reason.
* MLAAD is CC-BY-NC-4.0. A model trained with it is for research and coursework, not a commercial product.
* The vocoded Indic clips teach vocoder artefacts, not voice cloning. Report them separately rather than as an "Indic deepfake EER".
* The XTTS-v2 clones are under the Coqui Public Model License, which is non-commercial, like MLAAD. IndicF5 is MIT. Set `MAKE_CLONES=0` or drop `xtts` from `CLONE_ENGINES` for a training set without them.
* The dev-set threshold of the first run did not transfer to the test generators (65% of genuine clips flagged at that threshold), so calibrate thresholds on the full-corpus run before deploying.

## Team

Built by Hashim Bhagad (model training, evaluation and explainability tooling), Divyam Sanghvi (backend and integration) and Shreya Poojari (frontend).
