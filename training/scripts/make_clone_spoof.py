"""Generate zero-shot voice clones of speakers already in the bona-fide data.

WHY THIS EXISTS
---------------
The real-world tests showed the gap: off-the-shelf TTS voices were caught with
scores near 1.0, but clones of real people (the actual fraud scenario) scored
anywhere from 0.06 to 0.99, and the training data had no clones at all outside
Hindi (MLAAD). This script clones the voices of bona-fide speakers that are
already in the manifest, so every cloned speaker also has genuine recordings:

  * the model sees "same voice, real vs cloned" pairs and must learn the
    synthesis artefacts, because speaker identity no longer separates the classes;
  * build_manifest.py splits clones by speaker (--speaker-split-generators), so a
    speaker's real and cloned clips always land in the same split, and test
    clones are clones of people the model never heard.

ENGINES (zero-shot: a few seconds of reference audio, no per-speaker training)
  xtts     Coqui XTTS-v2. English + Hindi here (it has no Bengali/Tamil/Marathi).
           Coqui Public Model License: non-commercial use only.
  indicf5  AI4Bharat IndicF5 (F5-TTS trained on Indian languages). Hindi, Bengali,
           Tamil, Marathi. MIT licence; gated on Hugging Face (accept the terms).
           Needs the reference clip's transcript, which IndicVoices provides.

  language  engines            reference speakers
  hi        xtts + indicf5     IndicVoices speakers in data/candidates/indicvoices.csv
  bn/ta/mr  indicf5            "
  en        xtts               In-the-Wild / garystafford bona-fide speakers

Texts come from *other* utterances (other IndicVoices speakers' transcripts; the
FLEURS en_us train-split transcripts for English), so a clone never repeats the
reference clip's words.

Needs a GPU and the engine packages, which conflict with the training stack
(they pin NumPy < 2 and a newer Transformers). prepare_data.sh therefore runs
this in its own virtualenv (.clone-env). Run it from training/:

    python scripts/make_clone_spoof.py --engines xtts indicf5 --per-language 200
"""
from __future__ import annotations

import argparse
import inspect
import io
import json
import os
import random
import re
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

TRAINING_ROOT = Path(__file__).resolve().parents[1]
if str(TRAINING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRAINING_ROOT))

from src.ingest import ClipWriter, load_local_env, safe_name  # noqa: E402

INDIC = {"hindi": "hi", "bengali": "bn", "tamil": "ta", "marathi": "mr"}
ENGINES_FOR = {"hi": ("xtts", "indicf5"), "bn": ("indicf5",), "ta": ("indicf5",),
               "mr": ("indicf5",), "en": ("xtts",)}
GENERATOR = {"xtts": "xtts_v2_clone", "indicf5": "indicf5_clone"}
OUTPUT_RATE = {"xtts": 24000, "indicf5": 24000}
XTTS_MAX_CHARS = {"en": 240, "hi": 200}
FALLBACK_EN = [
    "Hi, it's me. I'm in a bit of trouble and I need you to send some money right away.",
    "Your account has been flagged for unusual activity, please confirm the code we just sent you.",
    "Can you call me back on this number? My phone is broken and I'm using a friend's.",
    "The meeting has moved to four o'clock, I'll send the details over email later today.",
    "Don't tell anyone yet, but I need the transfer done before the bank closes this evening.",
    "I just wanted to check whether the documents reached you, let me know when you get a moment.",
]


def clean_text(text: str) -> str:
    text = re.sub(r"\[[^\]]*\]|<[^>]*>|\{[^}]*\}", " ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip()


REF_RATE = 16000


def to_16k(wav: np.ndarray, rate: int) -> np.ndarray:
    """Keep references small in RAM: 16 kHz, at most 12 s (both engines resample anyway)."""
    import soxr

    if rate != REF_RATE:
        wav = soxr.resample(wav, rate, REF_RATE)
    return np.ascontiguousarray(wav[: 12 * REF_RATE], dtype=np.float32)


def decode(value) -> tuple[np.ndarray, int]:
    """Mono float32 + rate from an Audio(decode=False) cell (same as ingest_indicvoices)."""
    raw = value.get("bytes") if isinstance(value, dict) else None
    if raw is None and isinstance(value, dict) and value.get("path"):
        raw = Path(value["path"]).read_bytes()
    wav, rate = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    return wav.astype(np.float32), int(rate)


# --- reference and text collection -------------------------------------------

def indic_references(candidates: pd.DataFrame, language: str, revision: str | None, token: str,
                     speakers_needed: int, texts_needed: int, refs_per_speaker: int, seed: int):
    """Stream IndicVoices once: reference clips (+ transcripts) of our bona-fide speakers,
    and a pool of other speakers' transcripts to synthesise."""
    from datasets import Audio, load_dataset

    ours = set(candidates.speaker_id)
    refs: dict[str, list[tuple[np.ndarray, int, str]]] = defaultdict(list)
    texts: list[tuple[str, str]] = []  # (speaker, text)
    stream = load_dataset("ai4bharat/IndicVoices", language, split="train", streaming=True,
                          revision=revision, token=token)
    stream = stream.cast_column("audio_filepath", Audio(decode=False))
    for index, record in enumerate(stream):
        speaker = f"indicvoices:{safe_name(record.get('speaker_id') or f'unknown_{index}')}"
        text = clean_text(record.get("text") or record.get("normalized") or "")
        words = len(text.split())
        # Texts to synthesise come only from speakers we do NOT clone, so a clone never
        # says something its own speaker said in the data.
        if 4 <= words <= 30 and speaker not in ours:
            texts.append((speaker, text))
        duration = float(record.get("duration") or 0.0)
        have = sum(1 for v in refs.values() if v)
        wanted = bool(refs.get(speaker)) or have < speakers_needed  # only as many speakers as needed
        if (speaker in ours and wanted and len(refs.get(speaker, ())) < refs_per_speaker
                and 3.0 <= duration <= 12.0 and words >= 3):
            try:
                wav, rate = decode(record["audio_filepath"])
                refs[speaker].append((to_16k(wav, rate), REF_RATE, text))
            except Exception as exc:  # noqa: BLE001
                print(f"    ! unreadable reference: {exc}")
        full = sum(1 for v in refs.values() if len(v) >= refs_per_speaker)
        if (full >= speakers_needed and len(texts) >= texts_needed) or index > 200_000:
            break
    random.Random(seed).shuffle(texts)
    return dict(refs), texts


def english_references(candidates_dir: Path, data_root: Path, speakers_needed: int,
                       refs_per_speaker: int, seed: int):
    frames = [pd.read_csv(p) for p in sorted(candidates_dir.glob("*.csv"))
              if p.stem in {"in_the_wild", "garystafford"}]
    if not frames:
        return {}
    df = pd.concat(frames)
    df = df[(df.label == "bonafide") & (df.language == "en") & (df.duration_s >= 4.0)]
    speakers = sorted(df.speaker_id.unique())
    random.Random(seed).shuffle(speakers)
    refs = {}
    for speaker in speakers[:speakers_needed]:
        rows = df[df.speaker_id == speaker].head(refs_per_speaker)
        clips = []
        for clip in rows.clip_path:
            wav, rate = sf.read(str(data_root / clip), dtype="float32", always_2d=False)
            clips.append((to_16k(wav if wav.ndim == 1 else wav.mean(axis=1), int(rate)), REF_RATE, ""))
        refs[speaker] = clips
    return refs


def english_texts(n: int, seed: int) -> list[tuple[str, str]]:
    try:
        from huggingface_hub import hf_hub_download

        path = hf_hub_download("google/fleurs", "data/en_us/train.tsv", repo_type="dataset")
        rows = [line.split("\t") for line in Path(path).read_text(encoding="utf-8").splitlines()]
        texts = [clean_text(r[2]) for r in rows if len(r) > 2 and 6 <= len(r[2].split()) <= 30]
    except Exception as exc:  # noqa: BLE001
        print(f"  ! FLEURS transcripts unavailable ({exc}); using built-in sentences")
        texts = []
    texts = texts or FALLBACK_EN * (n // len(FALLBACK_EN) + 1)
    random.Random(seed).shuffle(texts)
    return [("fleurs", t) for t in texts[: max(n, 1) * 2]]


# --- engines -------------------------------------------------------------------

class XTTS:
    def __init__(self):
        if os.environ.get("COQUI_TOS_AGREED") != "1":
            raise SystemExit("XTTS-v2 is under the Coqui Public Model License (non-commercial). "
                             "Set COQUI_TOS_AGREED=1 to accept it, or drop xtts from --engines.")
        from TTS.api import TTS

        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

    def __call__(self, text, lang, ref_path, ref_text):
        text = text[: XTTS_MAX_CHARS.get(lang, 200)]
        return np.asarray(self.tts.tts(text=text, speaker_wav=ref_path, language=lang), dtype=np.float32)


class IndicF5:
    """IndicF5 loaded straight through its f5_tts package, not transformers.AutoModel.

    The hub wrapper (model.py) builds the model inside PreTrainedModel.__init__, which
    Transformers 5 runs on the "meta" device, and the vocoder set-up then fails. XTTS needs
    Transformers 5 in the same environment, so the weights are loaded here directly:
    model.safetensors holds the torch.compile'd EMA model ("ema_model._orig_mod.*") and
    the Vocos vocoder ("vocoder._orig_mod.*").
    """

    REPO = "ai4bharat/IndicF5"
    DIT = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)

    def __init__(self, token, workdir):
        import torch
        from f5_tts.infer.utils_infer import infer_process, load_model, load_vocoder, preprocess_ref_audio_text
        from f5_tts.model import DiT
        from huggingface_hub import hf_hub_download
        from safetensors.torch import load_file, save_file

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._infer, self._prep = infer_process, preprocess_ref_audio_text
        _patch_torchaudio_load()
        weights = hf_hub_download(self.REPO, "model.safetensors", token=token)
        vocab = hf_hub_download(self.REPO, "checkpoints/vocab.txt", token=token)
        state = load_file(weights)
        prefix = "ema_model._orig_mod."
        ema = {k[len(prefix):]: v.contiguous() for k, v in state.items() if k.startswith(prefix)}
        voc = {k[len("vocoder._orig_mod."):]: v for k, v in state.items() if k.startswith("vocoder._orig_mod.")}
        del state
        if not ema:
            raise RuntimeError(f"{self.REPO}: no ema_model weights found; the checkpoint layout changed")
        if "ckpt_path" in inspect.signature(load_model).parameters:
            # Upstream F5-TTS: load_model reads the checkpoint itself (expects "ema_model.*" keys).
            ckpt = Path(workdir) / "indicf5_ema.safetensors"
            save_file({"ema_model." + k: v for k, v in ema.items()}, str(ckpt))
            self.model = load_model(DiT, self.DIT, ckpt_path=str(ckpt), mel_spec_type="vocos",
                                    vocab_file=vocab, device=self.device)
            ckpt.unlink(missing_ok=True)
        else:
            # IndicF5's bundled f5_tts: load_model only builds the network; load the weights here.
            self.model = load_model(DiT, self.DIT, mel_spec_type="vocos", vocab_file=vocab, device=self.device)
            missing, unexpected = self.model.load_state_dict(ema, strict=False)
            missing = [k for k in missing if "mel_spec" not in k]  # STFT buffers are rebuilt in code
            if missing or unexpected:
                raise RuntimeError(f"IndicF5 weights do not fit the model: missing={missing[:5]} "
                                   f"unexpected={list(unexpected)[:5]}")
            self.model = self.model.to(self.device, dtype=torch.float32).eval()
        self.vocoder = load_vocoder(vocoder_name="vocos", is_local=False, device=self.device)
        if voc:
            self.vocoder.load_state_dict(voc, strict=False)

    def __call__(self, text, lang, ref_path, ref_text):
        ref_audio, ref_text = self._prep(ref_path, ref_text)
        audio, _rate, _ = self._infer(ref_audio, ref_text, text, self.model, self.vocoder,
                                      mel_spec_type="vocos", speed=1.0, device=self.device)
        return np.asarray(audio, dtype=np.float32)  # 24 kHz


def _patch_torchaudio_load() -> None:
    """f5_tts reads the reference with torchaudio.load, which in torchaudio >= 2.9 needs
    torchcodec (absent on Colab). Route it through soundfile for the WAVs we write."""
    import torch
    import torchaudio

    def load(path, *args, **kwargs):
        wav, rate = sf.read(str(path), dtype="float32", always_2d=True)
        return torch.from_numpy(np.ascontiguousarray(wav.T)), rate

    torchaudio.load = load


def plausible(audio: np.ndarray, rate: int, text: str) -> str | None:
    """Reject failed generations: silence, clipping noise, or runaway length."""
    seconds = len(audio) / rate
    if seconds < 1.0:
        return "shorter than 1 s"
    if seconds > max(20.0, 0.5 * len(text)):
        return f"runaway length ({seconds:.0f} s)"
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms < 1e-3:
        return "silent"
    if not np.isfinite(audio).all():
        return "non-finite samples"
    return None


# --- main ----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engines", nargs="+", default=["xtts", "indicf5"], choices=["xtts", "indicf5"])
    parser.add_argument("--languages", nargs="+", default=["hi", "bn", "ta", "mr", "en"],
                        choices=sorted(ENGINES_FOR))
    parser.add_argument("--per-language", type=int, default=200, help="clones per language")
    parser.add_argument("--max-per-speaker", type=int, default=4)
    parser.add_argument("--refs-per-speaker", type=int, default=2)
    parser.add_argument("--data-root", default=str(TRAINING_ROOT / "data"))
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--name", default="clones")
    args = parser.parse_args()

    load_local_env()
    token = os.environ.get("HF_TOKEN")
    data_root = Path(args.data_root).resolve()
    cand_dir = data_root / "candidates"
    iv_csv = cand_dir / "indicvoices.csv"
    iv = pd.read_csv(iv_csv) if iv_csv.exists() else pd.DataFrame(columns=["speaker_id", "language"])
    iv_meta = json.loads(iv_csv.with_suffix(".source.json").read_text()) if iv_csv.exists() else {}
    revision = iv_meta.get("revision")

    plan = {lang: [e for e in ENGINES_FOR[lang] if e in args.engines] for lang in args.languages}
    for lang, engines in plan.items():
        if not engines:
            print(f"skip {lang}: needs {ENGINES_FOR[lang]}, not in --engines")
    plan = {k: v for k, v in plan.items() if v}
    if not plan:
        raise SystemExit("nothing to do")

    speakers_needed = -(-args.per_language // args.max_per_speaker)
    work = []  # (lang, engine, speaker, ref(wav, rate, text), text)
    rng = random.Random(args.seed)
    for lang in plan:
        print(f"\n[{lang}] collecting references")
        if lang == "en":
            refs = english_references(cand_dir, data_root, speakers_needed, args.refs_per_speaker, args.seed)
            texts = english_texts(args.per_language, args.seed)
        else:
            name = next(k for k, v in INDIC.items() if v == lang)
            cand = iv[iv.language == lang]
            if cand.empty:
                print(f"  skip: no {name} speakers in {iv_csv.name}")
                continue
            refs, texts = indic_references(cand, name, revision, token, speakers_needed,
                                           2 * args.per_language, args.refs_per_speaker, args.seed)
        refs = {s: r for s, r in refs.items() if r}
        print(f"  {len(refs)} speakers with references, {len(texts)} candidate texts")
        if not refs or not texts:
            continue
        speakers = sorted(refs)
        rng.shuffle(speakers)
        text_iter = iter(texts)
        made = 0
        for round_ in range(args.max_per_speaker):
            for speaker in speakers:
                if made >= args.per_language:
                    break
                engine = plan[lang][made % len(plan[lang])]
                ref = refs[speaker][round_ % len(refs[speaker])]
                for other_speaker, text in text_iter:
                    if other_speaker != speaker:
                        break
                else:
                    text = None
                if text is None:
                    break
                work.append((lang, engine, speaker, ref, text))
                made += 1
        print(f"  planned {made} clones: {dict(Counter(e for l, e, *_ in work if l == lang))}")

    writer = ClipWriter(
        source_dataset=args.name,
        license_or_consent="synthetic clones: XTTS-v2 (Coqui Public Model License, non-commercial); "
                           "IndicF5 (MIT); references from IndicVoices (CC-BY-4.0) / In-the-Wild / garystafford",
        output_root=data_root, min_duration_s=1.0, max_duration_s=15.0,
    )
    engines: dict[str, object] = {}
    failed: dict[str, str] = {}
    stats = Counter()
    started = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        for i, (lang, engine, speaker, (ref_wav, ref_rate, ref_text), text) in enumerate(work, 1):
            if engine in failed:
                continue
            if engine not in engines:
                print(f"\nloading {engine} ...", flush=True)
                try:
                    engines[engine] = XTTS() if engine == "xtts" else IndicF5(token, tmp)
                except Exception as exc:  # noqa: BLE001 - keep the other engine's clones
                    failed[engine] = f"{type(exc).__name__}: {str(exc)[:300]}"
                    print(f"  ! {engine} could not be loaded, skipping its clones: {failed[engine]}")
                    continue
            ref_path = Path(tmp) / "ref.wav"
            sf.write(ref_path, ref_wav, ref_rate)
            try:
                audio = engines[engine](text, lang, str(ref_path), ref_text)
                problem = plausible(audio, OUTPUT_RATE[engine], text)
            except Exception as exc:  # noqa: BLE001 - one bad prompt must not kill the run
                problem = f"{type(exc).__name__}: {str(exc)[:120]}"
            if problem:
                stats[f"{engine}:rejected"] += 1
                if stats[f"{engine}:rejected"] <= 5:
                    print(f"  ! {engine}/{lang} {speaker}: {problem}")
            else:
                ok = writer.add(audio, OUTPUT_RATE[engine], stem=f"{lang}_{engine}_{i:05d}", label="spoof",
                                speaker_id=speaker, raw_speaker_id=True, language=lang,
                                attack_family="clone", generator=GENERATOR[engine],
                                noise_condition="clean", subdir=f"{engine}/{lang}")
                stats[f"{engine}:ok" if ok else f"{engine}:rejected"] += 1
            if i % 25 == 0 or i == len(work):
                rate = i / max(1e-6, time.time() - started)
                print(f"  {i}/{len(work)}  {dict(stats)}  {rate:.2f} clips/s", flush=True)
            for engine_name in GENERATOR:
                done = stats[f"{engine_name}:ok"] + stats[f"{engine_name}:rejected"]
                if (done >= 20 and stats[f"{engine_name}:rejected"] > 0.5 * done
                        and engine_name not in failed):
                    failed[engine_name] = f"more than half of {done} generations failed"
                    print(f"  ! {engine_name}: {failed[engine_name]}; skipping its remaining clones")

    if failed:
        print(f"\nengines that failed: {failed}")
    if not writer.rows:
        raise SystemExit("no clones were produced; see the messages above.")
    print("\n" + writer.summary())
    writer.write_candidate({
        "engines": args.engines, "languages": list(plan), "per_language": args.per_language,
        "max_per_speaker": args.max_per_speaker, "indicvoices_revision": revision,
        "stats": dict(stats), "failed_engines": failed,
        "note": "Zero-shot clones of bona-fide speakers in the manifest. speaker_id equals the "
                "cloned speaker's bona-fide id, so build_manifest.py keeps both in one split.",
    }, name=args.name)


if __name__ == "__main__":
    main()
