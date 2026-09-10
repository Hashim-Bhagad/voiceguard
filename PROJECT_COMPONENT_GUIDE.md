# VoiceGuard — Project Component Guide (for Jury Presentation)

> **One-line pitch:** VoiceGuard is a privacy-preserving, real-time system that listens to a live phone call, detects whether the voice on the line is a cloned or AI-generated impersonation, and blocks a high-risk action (like a wire transfer) until independent verification is done.

This document explains, in plain language:

1. **The problem** — why voice-cloning fraud is a real, growing threat.
2. **The solution** — what VoiceGuard is and how it works.
3. **Every component of the repo** — what each piece is, what it does, and how it fits together.
4. **The data flow** — step by step, what happens to an incoming call.

It is written so you can walk a jury through the entire system without assuming deep technical knowledge.

---

## 1. The Problem We Are Solving

Generative voice models ("voice cloning" / "deepfake audio") can now clone a person's voice from only a few seconds of publicly available audio — an earnings call, a podcast, a keynote, a YouTube video.

### 1.1 The attack scenario

1. A fraudster grabs a short clip of a real executive's voice (public audio).
2. They feed it to a voice-cloning model (text-to-speech / voice conversion).
3. They call the finance team *pretending to be the CEO*.
4. They use urgency and authority: *"Transfer ₹10 lakh immediately to this account — don't tell anyone, it's confidential."*
5. The voice **sounds exactly right** — humans cannot reliably tell the difference.

This is a **"vishing"** attack (voice phishing), and it is happening today against companies, banks, and individuals. Regulators, banks, and telecom providers have explicitly flagged voice-clone fraud as a top threat.

### 1.2 Why is it hard to stop?

- **A single signal is not enough.** A cloned voice may pass an acoustic check, and a real human scammer may pass a voice check. Fraudsters combine real voices, fake voices, and social engineering.
- **Static checks don't work.** A recording analyzed "later" in a fraud queue is too late — the money is already gone. Detection must happen **while the call is live**.
- **Privacy is a constraint.** Recording and storing every call's raw audio is legally and ethically problematic (e.g., India's DPDP Act 2023). The system should **not** keep raw audio by default.
- **No absolute guarantees.** No detector is 100% accurate. The answer is not "guaranteed detection" but **risk scoring + an enforced verification step** before a sensitive action completes.

### 1.3 The insight behind our solution

> **"How it sounds" + "what it says" + "who it matches" + "the context of the request" must all be checked together, and the final word should not be a single model — it should be an enforced step-up verification.**

That is exactly what VoiceGuard does.

---

## 2. The Solution: What VoiceGuard Is

**VoiceGuard** is a real-time, streaming anti-impersonation service. It analyzes live voice over several independent "lenses", fuses them into one calibrated risk score, and — when risk crosses a policy threshold — **interrupts the action** (holds a transaction) and triggers **challenge-response verification** (ask the caller to repeat a random phrase) plus out-of-band confirmation (OTP / callback).

### 2.1 The multi-view detection pipeline

| Lens | What it checks | Question it answers |
|---|---|---|
| **Acoustic / anti-spoofing (AASIST-L CNN)** | Micro-artifacts in the raw waveform left behind by synthetic speech (vocoder / spectral-temporal artifacts) | "Does the audio sound machine-generated?" |
| **Prosody / behavioral** | Pitch, rhythm, pauses, energy variation, voice quality (weak signals only) | "Does the speech have natural human variation, or is it oddly flat?" |
| **Linguistic / behavioral** | The live transcript for urgency, secrecy, authority, transaction language — in multiple languages (English, Hindi, Marathi, Tamil, Hinglish) | "Is the caller using social-engineering pressure tactics?" |
| **Speaker consistency** | Voice-print (embedding) match against an enrolled, known-good voice profile | "Is this the voice of the person they claim to be?" |
| **Context risk** | Caller ID, known contact, transaction amount, new payee, fraud-list flags, policy profile | "Does the *request itself* look risky?" |
| **Risk fusion** | Combines all of the above into one calibrated, time-smoothed `final_risk` score | "Overall, how risky is this call right now?" |
| **Policy engine** | Applies configurable thresholds per scenario (standard / high-value transaction / privileged access) | "What should we DO about it?" |
| **Challenge-response** | Asks the caller to repeat a random multilingual phrase, then verifies both the *words* (STT) and the *liveness* (acoustic score) | "Can a pre-rendered clone pass a live, unpredictable test?" |
| **Alerting & step-up** | In-app alerts, event logs, HOLD/OTP/callback escalation | "How do we stop the fraud from completing?" |

### 2.2 The two deployment modes (designed)

- **Server-Assisted mode:** audio frames stream over a WebSocket to the backend, which returns live risk telemetry 2–4× per second. Higher accuracy; used by banks, contact centers, and telecom.
- **Local-On-Phone mode (designed, privacy-first):** the same scoring runs on the device with zero audio leaving the phone. This is the strongest privacy story — offline, airplane-mode safe.

### 2.3 Privacy by design

- Audio is held in a **RAM-only ring buffer** (max ~8 seconds) and is **never written to disk by default** (`RETAIN_RAW_AUDIO=false`).
- Only **scores, events, and transcript excerpts** are retained (Firestore / in-memory).
- Consent + DPDP notice is part of the design; raw audio retention is a configurable mode, not the default.
---

## 3. Repository Structure (Monorepo)

The project is a monorepo with three top-level parts:

```
voice-guard/
├── backend/     # FastAPI service — the "brain" (streaming + REST APIs, scoring, alerts, persistence)
├── frontend/    # React + Vite web app — the "face" (marketing site + analyst dashboard)
├── training/    # AASIST-L CNN — the "learning" (data pipeline, fine-tuning, evaluation, ONNX export)
├── VOICEGUARD_TECHNICAL_IMPLEMENTATION.md   # the master technical/implementation plan
├── VoiceGuard_Internal_Hackathon_Plan.pdf   # the internal hackathon plan
├── voice_integrity_implementation_plan (1).docx  # earlier planning document
└── PROJECT_COMPONENT_GUIDE.md               # this document
```

```
backend/  app/  main.py, core/, api/v1/, schemas/, services/   + Docker, tests, scripts
frontend/ src/  App.jsx, components/, pages/, lib/              + Vite, ESLint
training/ src/  model.py, dataset.py  + configs/, scripts/, third_party/aasist/
```

---

## 4. Component Breakdown

### A. Backend — FastAPI anti-spoofing service (`backend/`)

The backend is the real-time analysis engine. It is a **FastAPI** application with a WebSocket streaming endpoint and REST endpoints, and it boots in **`mock` mode** by default so the UI can run before a trained model exists.

#### A.1 `backend/app/main.py` — Application entry point
- Builds the FastAPI app (`create_app()`), wires CORS, and mounts the four API routers under `/api/v1`.
- Adds the root route with pointers to `/docs` (auto-generated OpenAPI docs) and `/api/v1/health`.
- Uses a lazy lifespan: the ML model is loaded on first request, so cold start is fast.

#### A.2 `backend/app/core/config.py` — Central configuration
- Single source of truth read from environment variables (`.env`).
- Key settings: `MODEL_BACKEND` (`mock` or `aasist-l-onnx`), model path (`models/aasist-l-indic-v0.1.onnx`), model/policy versions, CORS origins, `RETAIN_RAW_AUDIO`, Firestore credentials path, and Groq API key.
- Used everywhere via a cached `get_settings()`.

#### A.3 `backend/app/schemas/contracts.py` — The frozen API contract
- Defines the **versioned data contract** shared by streaming and REST: `InitMessage`, `Telemetry`, `VerifyResponse`, `EnrollRequest`, and the policy threshold defaults.
- Key enums:
  - **Policy profiles:** `standard`, `high-value-txn`, `privileged-access` (different risk thresholds).
  - **Risk states:** `insufficient`, `low`, `review`, `high`.
  - **Actions:** `continue`, `verify`, `hold`, `challenge`.
- Comment says it best: *"FROZEN v1 streaming + REST contract. Do not rename fields — bump version instead."*
#### A.4 `backend/app/api/v1/` — The HTTP/WebSocket endpoints

| File | Endpoint(s) | What it does |
|---|---|---|
| `health.py` | `GET /api/v1/health` | Reports service status, active model backend, model version, policy version, and whether raw audio is retained. Used by the dashboard and by Docker's healthcheck. |
| `stream.py` | `WS /ws/stream` | The **live streaming path**: client sends a JSON `init` message, then binary PCM16 audio frames, and receives JSON risk telemetry ~2–4×/sec. This is the heart of "real-time detection." |
| `verify.py` | `POST /api/v1/verify/file` | The **batch / file path**: upload an audio file (WAV/MP3/etc.), get a full `VerifyResponse` — transcript, acoustic score, linguistic score, prosody, fused risk, state, action, flags, and whether a challenge was triggered. Persists session + alert records. |
| `aux.py` | `/enroll`, `/policy`, `/challenge/create`, `/challenge/verify`, `/challenge/verify-audio`, `/sessions`, `/alerts`, `/events`, `/events/emit` | Auxiliary APIs: enroll a known-good voice profile, read policy thresholds, create/verify challenges, list recent sessions & alerts, and inspect/emit events. |

#### A.5 `backend/app/services/` — The detection modules (the "why")

| Module | What it does | Status in code |
|---|---|---|
| `model_registry.py` | The **acoustic anti-spoofing scorer**. Loads the AASIST-L ONNX model (CPU), pads/picks a fixed 64,600-sample @16 kHz window, converts the model's `spoof_logit` to a calibrated spoof probability in [0,1] (higher = more spoof-like). Falls back to a mock heuristic for UI development when the model isn't present. | Real model path implemented; mock default |
| `ring_buffer.py` | A bounded, **RAM-only** buffer that keeps the last ~8 seconds of audio and returns sliding analysis windows (e.g., 1.5 s). **Never touches disk** — this is the core of the privacy story. | Complete |
| `preprocess.py` | Converts incoming PCM16 bytes → float32 mono @16 kHz, normalized to a target RMS level. | Complete |
| `vad.py` | **Voice Activity Detection + quality gate.** Decides whether a window contains speech (RMS-based for now; Silero swap planned) and flags quality (`ok` / `insufficient`). Prevents scoring silence. | Mock energy VAD; Silero planned |
| `prosody.py` | **Prosody/behavioral analysis** — flags speech as `flat` / `normal` / `unknown` based on signal variance (placeholder for F0/pause/HNR analysis). **Never standalone reject** — a weak signal only. | Placeholder heuristic |
| `linguistic.py` | **Multilingual urgency analysis.** Scans the transcript against urgency/secrecy/transaction lexicons in English, Hindi, Marathi, Tamil, and Hinglish (e.g., "transfer now", "don't tell anyone", "तुरंत", "உடனே", "otp bata"). Returns a linguistic risk score + matched flags. | Rule-based (v1), ML upgrade planned |
| `speaker.py` | **Speaker consistency.** Enrolls a known-good voice embedding (ECAPA planned) and returns a match score (mock: neutral). Kept **separate** from the spoof score so "is it synthetic?" and "is it the right person?" are reported independently. | Mock store; ECAPA planned |
| `fusion.py` | **Risk fusion engine.** Combines acoustic + linguistic + context (+ prosody, + speaker mismatch) with transparent, versioned weights into a single score, smooths it over time (EMA), and applies the **policy profile thresholds** to emit `state` + `action` (`low→continue`, `review→verify`, `high→hold`). | Complete (stub weights) |
| `alerts.py` | **Alert bus.** Emits in-app/log events when a session goes `high` (logs a warning with HOLD guidance). SMS/push/email gateway is a planned stub. | Basic implemented |
| `challenge.py` | **Challenge-response verification.** Generates a truly random multilingual phrase (e.g., `7-3-neela-9`), enforces a strict 30-second expiry, then verifies a spoken response by (1) transcribing it with Whisper STT, (2) checking token match, and (3) running the acoustic anti-spoof model on the response to catch replayed/synthetic audio. Clears the challenge after use to prevent replay. | Fully implemented |
| `stt.py` | **Speech-to-Text** via the Groq Whisper cloud API (`whisper-large-v3-turbo`), with language hint support. Feeds the linguistic and challenge paths. | Implemented (requires API key) |
| `audio_utils.py` | **Audio decoding/normalization.** Converts arbitrary input (WAV, PCM16, WebM/OGG/FLAC via soundfile) to canonical 16 kHz mono float32 in [-1,1]. Used by file verification and challenge audio. | Complete |
| `firestore_service.py` | **Persistence.** Saves session logs and alerts to Google Firestore (scores/transcripts/metadata only — **no raw audio**), with an automatic **in-memory fallback** when no service account key is present. Powers the session-log/alerts views. | Complete + fallback |

#### A.6 `backend/scripts/`
- `benchmark.py` — measures streaming-path latency (p50/p95) and time-to-first-score on the current machine.
- `download_models.py` — verifies the single Colab-exported AASIST-L ONNX model is present in `backend/models/`.

#### A.7 `backend/` infrastructure
- `Dockerfile` + `docker-compose.yml` — containerized API with healthcheck; mounts `backend/models/` so the trained ONNX can be swapped in without rebuilding.
- `pyproject.toml` + `uv.lock` — Python project managed with `uv`; `full` extra includes torch/onnx/soundfile; `dev` includes pytest/httpx/ruff.
- `tests/test_contract.py` — contract tests: health endpoint returns OK, fusion thresholds produce `high`/`low`, and the verify endpoint enforces its schema.
- `.env.example` — template for environment config (no secrets committed).
---

### B. Frontend — React + Vite web app (`frontend/`)

The frontend is the **user-facing "face"**: a polished marketing site that explains the product, plus an **analyst dashboard** that demonstrates live monitoring, alerts, challenge-response, and session logs. It runs in the browser with the backend in mock mode, so the whole demo works end-to-end even before the trained model is deployed.

Tech: React 19, Vite, React Router, GSAP (scroll animations), Motion (loader), Firebase SDK.

#### B.1 Routing (`src/App.jsx`, `src/main.jsx`)
- `/` — the marketing landing page.
- `/dashboard/*` — the analyst dashboard, wrapped in one shared `AnalysisProvider` so all pages share live call state: `/dashboard` (Live Monitoring), `/dashboard/alert`, `/dashboard/challenge`, `/dashboard/log`.

#### B.2 Shared state (`src/lib/AnalysisContext.jsx`)
- A React context that simulates running an analysis: `idle → analyzing → complete/error`, returning a mock analysis result (acoustic risk, linguistic risk, final risk, transcript, flags, challenge-triggered). This lets the dashboard demo work standalone; the real data comes from the backend contract.

#### B.3 Landing-page components (`src/components/`)
| Component | What it does |
|---|---|
| `Loader.jsx` | Animated intro loading screen (equalizer bars + progress), exits when complete. |
| `CursorGrid.jsx` | Ambient cursor-following background grid (visual polish). |
| `Navbar.jsx` | Top navigation with scroll styling, links to sections/dashboard, and a "Request demo" modal. |
| `Hero.jsx` | Opening headline + CTA, with GSAP character reveal animation. |
| `ProblemSection.jsx` | **Tells the jury the problem**: "Your CEO's voice can be faked in seconds," with a scroll-triggered phone animation. |
| `PhoneMockup.jsx` | Reusable animated phone frame showing `STANDBY` / `ANALYZING` states — the visual centerpiece used across sections. |
| `FeatureExplainer.jsx` | Scroll-pinned section walking through the **4-step solution**: 1) Acoustic Analysis, 2) Linguistic Analysis, 3) Risk Fusion, 4) Challenge Response. This is the "how it works" narrative. |
| `SpecsSection.jsx` | Four selling points: real-time detection, multilingual/accent-aware, no raw audio stored, API-first integration. |
| `SessionLogPreview.jsx` | Auto-playing carousel of recent analyzed calls with risk scores/verdicts. |
| `DocsSection.jsx` | Shows the public API response shape (`POST /analyze`) — signals API-first integration. |
| `Footer.jsx` | CTA ("Watch VoiceGuard catch a clone in real time"), marquee, socials, demo modal. |

#### B.4 Dashboard pages (`src/pages/`)
| Page | What it does |
|---|---|
| `LiveMonitoring.jsx` | **Live Monitoring** — upload a recording, record from mic, or use a sample call; shows waveform, live transcript, flags, risk-breakdown bars (Acoustic / Linguistic / Fused), verdict badge, and challenge status. |
| `AlertBanner.jsx` | **Alert** — shows a color-coded alert card when fused risk crosses a threshold, with transcript and flags. |
| `ChallengeResponse.jsx` | **Challenge-Response** — displays a generated code and simulates listening/verifying/pass/fail states (live version is wired to the backend challenge endpoints). |
| `SessionLogPage.jsx` | **Session Log** — table of analyzed calls (time, caller, risk %, verdict), with the current session prepended after an analysis runs. |
| `AudioInput.jsx` | Shared input control (upload / record / sample) used by the dashboard. |
---

### C. Training — AASIST-L anti-spoofing CNN (`training/`)

This is the **machine-learning core**: how we produce the one acoustic model that detects synthetic voice. It is a disciplined, reproducible pipeline around a single chosen architecture: **AASIST-L** (Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks) from ClovaAI — deliberately the *only* deployable acoustic model in the project.

#### C.1 Why AASIST-L
- AASIST-L is a compact (~85K params) raw-waveform network that models **spectro-temporal artifacts** left by neural vocoders — precisely the fingerprints of cloned speech.
- It is small enough to run on a phone via ONNX Runtime Mobile and fast enough for streaming on a CPU.
- We fine-tune it on **Indian-language bona-fide vs spoof** data (Hindi, Indian English, Marathi, Tamil) so accuracy holds for Indian callers — not just English.

#### C.2 `src/model.py` — Model adapter
- A thin wrapper that loads the **pinned official AASIST source** (checked out at an immutable commit), validates the config, loads pretrained checkpoints, and adds a `SpoofLogitExport` wrapper that emits exactly the `spoof_logit` the backend expects.
- Model contract: input `waveform: float32[batch, 64600]` @16 kHz; output `spoof_logit: float32[batch]` (positive = more spoof-like).

#### C.3 `src/dataset.py` — Data loading + augmentation
- Loads a validated `metadata.csv` manifest and enforces **split discipline** (speaker-disjoint train/dev/test, held-out spoof generators, labels exactly `bonafide`/`spoof`).
- Produces 16 kHz, 64,600-sample windows, with **label-neutral** augmentation: narrowband (8 kHz) round-trip, noise mixing (MUSAN-style), room-impulse-response convolution, and gain — so the model learns channel robustness, not augmentation artifacts.

#### C.4 `configs/aasist_l.yaml` — Training config
- Single source of truth: seed, sample rate, model architecture (AASIST-L hyperparameters), data splits, batch size, augmentation probabilities, and training schedule (30 epochs, cosine decay, early stopping, mixed precision, gradient clipping).

#### C.5 The pipeline scripts (`training/scripts/`)
| Script | What it does |
|---|---|
| `bootstrap_aasist.py` | Clones the official AASIST repo at a **pinned, immutable revision** (reproducibility). |
| `download_pretrained.py` | Downloads the reviewed public AASIST-L checkpoint (initialization weights). |
| `inspect_hf_dataset.py` | Inspects Hugging Face dataset configs/revisions before use. |
| `collect_hf_bonafide.py` | Streams a capped, provenance-recorded bona-fide subset (e.g., from AI4Bharat IndicVoices) into candidate CSVs with source revision metadata. |
| `download_hf_dataset.py` | Snapshots an approved HF dataset at a resolved revision, recording provenance. |
| `assemble_full_manifest.py` | Merges reviewed candidate CSVs into the validated `metadata.csv`, enforcing split/speaker/generator rules. |
| `validate_manifest.py` | Validates labels, paths, speaker splits, and generator holdout before any training. |

#### C.6 Training / evaluation / export (run on Colab GPU)
- `train_aasist_l.py` — fine-tunes AASIST-L with mixed precision, cosine LR decay, gradient clipping, and **dev-EER early stopping**; saves `best.pt`.
- `eval.py` — computes EER, ROC-AUC, PR-AUC on a held-out test set using a dev-derived threshold, plus **per-group** FPR/FNR (by language, attack family, generator, codec, noise) for bias/robustness reporting.
- `export_onnx.py` — exports the trained model to ONNX (`aasist-l-indic-v0.1.onnx`) with a **PyTorch↔ONNX numerical equivalence check**; this file is copied to `backend/models/` and served by the backend via ONNX Runtime (CPU only — no GPU needed).

#### C.7 `third_party/aasist/` — Pinned upstream
- The official ClovaAI AASIST source (models, configs, evaluation) checked out at a pinned commit, including the pretrained `AASIST-L.pth` / `AASIST.pth` weights used as initialization.

#### C.8 Data plan
- Genuine speech: AI4Bharat IndicVoices (train), IndicVoices-R (dev/test), Lahaja (Hindi holdout), Svarah (Indian-English holdout) — all with license/consent tracking.
- Synthetic/spoof speech: consented TTS (e.g., IndicF5 / family A), voice conversion, replay, and partial inserts — with generator-disjoint train/dev/test so generalization is honestly measured.
- Target: ~3,000–5,000 balanced clips across 4 languages for the first credible run.

---

### D. Planning documents (`/` root)

| Document | What it is |
|---|---|
| `VOICEGUARD_TECHNICAL_IMPLEMENTATION.md` | The **master technical plan**: PS requirement traceability, threat model, architecture, module specs (streaming, VAD, acoustic CNN, prosody, linguistic, speaker, fusion, policy, alerts, challenge-response), APIs, privacy/DPDP, dataset + training plan, evaluation, limitations, references, and the demo script. |
| `VoiceGuard_Internal_Hackathon_Plan.pdf` | The internal hackathon planning deck (scope, milestones, day-split). |
| `voice_integrity_implementation_plan (1).docx` | An earlier planning document for the voice-integrity implementation. |
---

## 5. End-to-End Data Flow (how a live call is analyzed)

```
 Caller speaks
      │
      ▼
 [Frontend / client]  mic or uploaded file
      │  binary PCM16 frames over WebSocket
      ▼
 ┌────────────────────────────── BACKEND (FastAPI) ──────────────────────────────┐
 │  WS /ws/stream                                                               │
 │   init (session, policy profile) → loop over frames:                        │
 │                                                                              │
 │   1. preprocess.pcm16_to_float32 + normalize                                │
 │   2. ring_buffer.append (RAM only, last ~8s)                                │
 │   3. vad.is_speech + quality check → "insufficient"? → send telemetry, wait │
 │   4. window = ring_buffer.window(1.5s)                                      │
 │   5. model_registry.score_spoof(window)   ← AASIST-L acoustic anti-spoof   │
 │   6. prosody.prosody_flag(window)         ← flat/normal/unknown            │
 │   7. linguistic.score_text(transcript)    ← urgency lexicons (multilingual)│
 │   8. speaker.match_score(...)             ← identity consistency           │
 │   9. context_risk (caller/txn/policy profile)                              │
 │  10. fusion.fuse(...) → final_risk + state + action                        │
 │        low    → continue                                                   │
 │        review → verify (independent channel)                               │
 │        high   → hold + alert + challenge                                   │
 │  11. send telemetry JSON back (~2–4×/sec)                                  │
 │                                                                              │
 │  When high: alerts.emit + (optional) Firestore session/alert records        │
 │  Challenge path: create random phrase → caller responds → STT + token match │
 │                   + acoustic liveness check → pass/fail/uncertain           │
 └──────────────────────────────────────────────────────────────────────────────┘
      │
      ▼
 [Frontend dashboard]  risk bars, verdict, flags, challenge status, session log
```

### The batch path (investigation / regression)
Upload a recording → `POST /api/v1/verify/file` → decode to 16 kHz mono → (auto) Whisper transcript → acoustic score → linguistic score → prosody → context → fusion → persist session (and alert if high) → full `VerifyResponse` with flags and challenge-triggered status.

---

## 6. Current Status & Honest Framing (important for the jury)

- **The full pipeline works end-to-end today** in **mock mode**: the UI, streaming, fusion, policy, alerts, challenge, Firestore persistence, and STT are all implemented. The acoustic model has a deterministic mock fallback so the demo runs anywhere.
- **The real acoustic model path is built and verified**: the backend loads the AASIST-L ONNX via ONNX Runtime (CPU), and the training pipeline produces that ONNX with a numerical equivalence check. The missing piece is simply the *fine-tuned* model, which requires the Colab GPU run against the licensed Indic dataset (a deliberate, governed step).
- **Honest claims**: AASIST-L initialized from ASVspoof checkpoint gives a baseline, but Indic performance must be measured on our held-out test set before production claims. Challenge-response is a **step-up cost, not proof** — it must pair with OTP/callback. We do not claim "100% detection" or "zero false positives."
- **Privacy stance**: raw audio is not written to disk by default; only scores/events/transcript excerpts are retained; consent + DPDP notice are part of the design.
---

## 7. Glossary (jury-friendly)

| Term | Plain meaning |
|---|---|
| **Anti-spoofing** | Detecting whether audio is genuine or machine-generated/fake. |
| **AASIST-L** | The chosen neural-network model that reads raw sound and scores how "synthetic" it is. |
| **ONNX** | An open model-exchange format; lets the same model run on a server or phone via ONNX Runtime. |
| **WebSocket** | A persistent two-way connection; used to stream audio up and telemetry down in real time. |
| **VAD (Voice Activity Detection)** | Knowing when a person is actually speaking vs. silence/noise. |
| **STT / Whisper** | Speech-to-text — turning the caller's words into a transcript for analysis. |
| **Prosody** | The rhythm, pitch, and flow of speech — flat/predictable prosody can hint at synthesis. |
| **Speaker embedding** | A mathematical "voiceprint" of a person's voice, used for identity consistency checks. |
| **Risk fusion** | Combining several independent signals into one overall score with explicit weights. |
| **Policy profile** | A set of thresholds deciding how sensitive a scenario is (e.g., a ₹10L transfer is more sensitive than a ₹500 one). |
| **Challenge-response** | Asking the caller to repeat a random phrase to prove liveness; a pre-recorded clone can't answer an unpredictable question in real time. |
| **DPDP Act 2023** | India's data-privacy law; our design follows minimize-retention / consent principles (legal review still required). |
| **EER** | Equal Error Rate — a standard accuracy metric for anti-spoofing (lower is better). |

---

## 8. Suggested 60–90 Second Jury Walkthrough

1. **Problem (15s):** "A CEO's voice can be cloned from a few seconds of public audio. Fraudsters use it to call finance teams and rush through wire transfers — and the voice sounds perfect."
2. **Solution (20s):** "VoiceGuard analyzes live calls through multiple lenses — how it sounds, what it says, who it matches, and the context of the request — and fuses them into one real-time risk score."
3. **Live demo (30s):** Show the dashboard — play a genuine clip → green/low; play a cloned clip with urgency language → curve rises → `review → high` → HOLD + challenge card triggered.
4. **Privacy (10s):** "No raw audio is stored — only scores and transcript excerpts. Local mode keeps audio on the phone entirely."
5. **Depth (15s):** "The acoustic model is a fine-tuned AASIST-L CNN exported to ONNX; the same file runs on server and phone. Everything is versioned, evaluated per-language, and honestly scoped."