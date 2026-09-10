# Training — AASIST-L, multilingual, local

VoiceGuard uses one acoustic model everywhere: the official
[ClovaAI AASIST-L](https://github.com/clovaai/aasist) raw-waveform anti-spoofing
model (85,306 parameters). This directory fine-tunes it **on your own machine**,
exports one ONNX file, and that same file runs under ONNX Runtime on the FastAPI
server, a CPU laptop, and a phone.

There is no Colab step. `runtime.device: auto` uses CUDA when it is present and
CPU otherwise.

XLS-R, RawNet, WavLM and ensembles are not part of this pipeline.

---

## 1. Environment

Python 3.12 is used because it has the widest wheel coverage across torch,
onnxruntime and librosa. `uv` will fetch it if needed.

```bash
cd training

uv venv --python 3.12 .venv

# torch from the CPU index, so you do not download ~2.5 GB of unused CUDA wheels
uv pip install --python .venv/bin/python \
    --index-url https://download.pytorch.org/whl/cpu "torch~=2.9"
uv pip install --python .venv/bin/python -r requirements-local.txt
```

`requirements-local.lock.txt` holds the exact versions this was verified against
(Python 3.12.14, torch 2.14.0+cpu).

Fetch the pinned upstream source and its released checkpoint:

```bash
.venv/bin/python scripts/bootstrap_aasist.py      # clones clovaai/aasist at a pinned commit
.venv/bin/python scripts/resolve_pretrained.py    # copies + verifies weights/AASIST-L.pth
```

`resolve_pretrained.py` asserts the checkpoint loads into the pinned architecture
with zero missing or unexpected keys. Those weights were trained on ASVspoof 2019
LA (English, older codecs) — they are an initialisation, not an Indic result.

Sanity check the library code at any time:

```bash
.venv/bin/python tests/test_src.py
.venv/bin/python tests/test_ingest.py
```

---

## 2. Credentials

Copy `.env.example` to `.env` and fill in what you need. `.env` is gitignored.

```
HF_TOKEN=hf_...
```

A read-only Hugging Face token is enough. IndicVoices is a **gated** dataset:
accept its terms on the dataset page once, with the same account, before
ingesting. Never commit `.env` or paste the token into a notebook.

---

## 3. Data

Download only what you are licensed to use, and keep the provenance record each
ingest script writes next to its output.

| Source | Role | Licence | Notes |
|---|---|---|---|
| [AI4Bharat IndicVoices](https://huggingface.co/datasets/ai4bharat/IndicVoices) | Indic bona-fide | CC-BY-4.0, gated | 22 Indian languages. **No English config exists.** |
| [garystafford/deepfake-audio-detection](https://huggingface.co/datasets/garystafford/deepfake-audio-detection) | English bona-fide + 6 TTS families | CC-BY-4.0 | 933 real / 933 fake, 16 kHz FLAC |
| [In-the-Wild](https://huggingface.co/datasets/mueller91/In-The-Wild) | Real-world generalisation set | CC-BY-SA-4.0 | 58 celebrities, 37.9 h. Ungated mirror of the Kaggle set, so no Kaggle login needed |

Each `scripts/ingest_*.py` normalises audio to 16 kHz mono WAV under
`data/audio/`, then writes a candidate CSV plus a `.source.json` recording the
resolved dataset revision.

```bash
.venv/bin/python scripts/ingest_garystafford.py
.venv/bin/python scripts/ingest_in_the_wild.py                 # ~7 GB download
.venv/bin/python scripts/ingest_indicvoices.py \
    --languages hindi marathi tamil bengali --max-per-language 400
```

Candidate CSVs deliberately have **no `split` column**. Splits are assigned once,
globally, in step 4.

### Read this before you trust any number

These three sources put **every Indic clip on the bona-fide side and every spoof
clip in English**. A classifier can then score a near-zero EER by learning
"sounds Indic → genuine", and it will miss real Hindi or Tamil clones in
production. Two partial mitigations are wired in:

* English appears on *both* sides, because garystafford and In-the-Wild each
  supply real English as well as fake.
* `scripts/make_vocoded_spoof.py` puts Indic audio on the spoof side by
  re-synthesising held-out IndicVoices speakers through a vocoder-style
  analysis/resynthesis pass:

```bash
.venv/bin/python scripts/make_vocoded_spoof.py --max-per-language 200
```

Those clips are **not voice clones** — content and speaker identity are
unchanged, only the signal path is synthetic. They teach the model to react to
vocoder artifacts in Indic languages, which is the shared final stage of
essentially every TTS and voice-conversion system. They are labelled
`attack_family=vocoded` so you can report them separately or drop them. Do not
publish an "Indic deepfake detection EER" that rests on them. To make a real
claim you need consented Indic TTS/VC clips registered as their own generators.

---

## 4. Manifest

```bash
.venv/bin/python scripts/build_manifest.py --check-files \
    --dev-generators elevenlabs \
    --test-generators speechify in_the_wild_unknown
```

This pools the candidate CSVs and assigns `train`/`dev`/`test` under three
constraints, then validates through the same code path training uses:

1. **Speaker-disjoint** — all of a speaker's clips land in one split, so the model
   cannot recognise the voice instead of the artifacts.
2. **Generator holdout** — whole TTS/VC families are reserved for dev and test, so
   the reported EER measures generalisation to an unseen synthesiser rather than
   in-generator recall.
3. **Per-language label coverage** — it prints a warning for every language that
   appears with only one label, because that is the confound above.

Re-validate an existing manifest at any time:

```bash
.venv/bin/python scripts/validate_manifest.py --metadata-csv data/metadata.csv --check-files
```

---

## 5. Train

```bash
.venv/bin/python train_aasist_l.py \
    --config configs/aasist_l.yaml \
    --pretrained weights/AASIST-L.pth
```

Laptop-friendly behaviour:

* Writes `last.pt` every epoch; `--resume` continues from it with optimiser,
  scheduler and epoch state intact.
* `train.max_hours` stops cleanly on a wall-clock budget so a long run can be
  split across sittings.
* `runtime.cache_dir` caches decoded 16 kHz audio as `.npy`, so only the first
  epoch pays FLAC decode and resampling.
* `data.balanced_sampler` samples batches inversely to (label × language)
  frequency, so a big English spoof corpus next to a smaller Indic bona-fide
  corpus does not make "English" and "spoof" correlated within a batch.
* Per-epoch metrics go to `outputs/<run>/history.csv`, plus a `summary.json`.

Augmentation (narrowband round trip, additive noise, RIR, gain) is applied
**identically to both labels**. Applying it to one class would make the
augmentation itself the discriminative feature. If `augmentation.noise_dir` or
`rir_dir` is absent, the loader warns and substitutes a synthetic generator
rather than silently disabling the augmentation.

### Measured CPU cost, and why batch size matters more than you'd expect

Run `scripts/benchmark_cpu.py` on your own machine before planning a long run. It
caps its own address space with `RLIMIT_AS`, so a bad probe dies alone instead of
inviting the OOM killer.

On the reference machine (Intel i5-12450H, 12 logical cores, 15 GiB RAM, no
NVIDIA GPU):

| batch | peak RSS |
|---|---|
| 1 | 0.77 GiB |
| 2 | 1.19 GiB |
| 4 | 1.95 GiB |
| 6 | 2.69 GiB |

AASIST-L has 85,306 parameters but costs roughly **0.19 GiB of peak RSS per clip
in the batch**, because the sinc-conv front end emits a `(batch, 70, 64472)` map
and the first encoder block expands it to `(batch, 32, 23, 21490)` — about 1 GiB
for one tensor at batch 16, before autograd saves what it needs for backward.
Batch 16 was OOM-killed at 5.1 GiB on this laptop. Note that zram swap is
compressed RAM, so it is not real headroom.

Throughput, at the safe batch:

| threads | train clips/s | infer clips/s |
|---|---|---|
| 4 | 1.52 | 3.29 |
| 8 | **1.54** | 3.59 |
| 12 | 1.30 | 3.38 |

Two things follow. Thread scaling is essentially flat past 4 and **regresses at
12**, so do not oversubscribe. And throughput is the same at batch 4 as at batch
16, so the small batch costs nothing here — `batch_size: 4` with
`grad_accum_steps: 4` keeps the effective batch at 16 for the same wall clock and
a third of the memory.

Projected wall clock at 1.54 clips/s:

| train clips | 1 epoch | 8 epochs |
|---|---|---|
| 1,108 | 13.4 min | 1.8 h |
| 4,000 | 45 min | 6.0 h |
| 8,000 | 88 min | 11.8 h |
| 30,000 | 5.4 h | 43.6 h |

So the full three-source corpus is a multi-day CPU run, not an afternoon. Use
`train.max_hours` with `--resume` to split it across sittings, or cap the corpus
with `build_manifest.py --max-per-source-label N` for a first pass.

---

## 6. Evaluate

```bash
.venv/bin/python eval.py --ckpt outputs/aasist_l_indic/best.pt --save-scores
```

The threshold comes from `dev`; the headline EER is on `test`, whose spoof
generators were never seen in training. Per-language and per-generator FPR/FNR
are printed by default, along with a per-language EER wherever a language has
both labels. A high overall score with a bad Indic breakdown is the failure mode
to watch for.

---

## 7. Export

```bash
.venv/bin/python export_onnx.py --ckpt outputs/aasist_l_indic/best.pt \
    --out aasist-l-indic-v0.1.onnx
```

The ONNX contract the backend expects:

| | |
|---|---|
| input | `waveform` `float32[batch, 64600]`, 16 kHz mono, in `[-1, 1]` |
| output | `spoof_logit` `float32[batch]`, positive means more spoof-like |

Export is verified against PyTorch at batch 1 and batch 3 (the second call also
proves the dynamic batch axis works) and refuses to write an unverified file.
Then copy it to `backend/models/`, set `MODEL_BACKEND=aasist-l-onnx`, and restart
the backend.

---

## Files

| Path | Purpose |
|---|---|
| `scripts/bootstrap_aasist.py` | Clone official AASIST at a pinned revision |
| `scripts/resolve_pretrained.py` | Resolve + verify `AASIST-L.pth` from that clone |
| `scripts/inspect_hf_dataset.py` | Inspect a HF dataset's configs and files |
| `scripts/ingest_indicvoices.py` | Stream capped Indic bona-fide clips |
| `scripts/ingest_garystafford.py` | English real + 6 TTS families, generator from filename |
| `scripts/ingest_in_the_wild.py` | Real-world English benchmark |
| `scripts/make_vocoded_spoof.py` | Indic vocoder-resynthesis spoof (auxiliary only) |
| `scripts/build_manifest.py` | Global speaker-disjoint split + generator holdout |
| `scripts/validate_manifest.py` | Re-check an existing manifest |
| `src/ingest.py` | Shared ingest layer, incl. verified downloads |
| `src/dataset.py` | Manifest loading, 64,600-sample windows, label-neutral augmentation |
| `src/model.py` | Adapter for only the official AASIST-L architecture |
| `train_aasist_l.py` | Device-agnostic fine-tuning with resume and time budget |
| `eval.py` | Dev-thresholded test EER plus group breakdowns |
| `export_onnx.py` | Verified ONNX export |
| `tests/` | Runnable checks for the above (plain python, no pytest) |

Downloads are verified for completeness, not just for a zero exit code.
`huggingface_hub` falls back to returning an existing partial `local_dir` when the
API becomes unreachable mid-transfer, which once silently produced 241 of 933
real clips with exit status 0 — a skew that would have quietly corrupted training.
`src/ingest.download_snapshot` resolves the authoritative file list first and
loops until every expected file is on disk.

Do not report an accuracy, latency, quantisation or phone-compatibility claim
until the exported model has been measured on your held-out test split and on the
actual target devices. Source descriptions above were rephrased for compliance
with licensing restrictions.
