"""Channel augmentations: lossy codec round trips and RawBoost.

Both are applied identically to bona-fide and spoof clips (see Augmenter in
src/dataset.py), so neither can become a label shortcut. They target the two
gaps the real-world tests exposed:

* **Codecs.** Genuine speech that had been through WhatsApp-style Opus was
  flagged as fake far more often than clean speech, because nothing in training
  had been compressed. ``codec_roundtrip`` encodes and decodes a clip in memory
  through Opus, MP3, AAC or G.711 at call/messaging bitrates.

* **RawBoost** (Tak, Kamble, Patino, Todisco, Evans, "RawBoost: A Raw Data
  Boosting and Augmentation Method applied to Automatic Speaker Verification
  Anti-Spoofing", ICASSP 2022, https://arxiv.org/abs/2111.04433). Three
  data-agnostic nuisance models on the raw waveform: linear and non-linear
  convolutive noise (LnL), impulsive signal-dependent noise (ISD) and stationary
  signal-independent noise (SSI). The wav2vec 2.0 + AASIST results this model
  follows were trained with it. Reimplemented here from the paper and the
  reference code (https://github.com/TakHemlata/RawBoost-antispoofing) using
  the paper's default parameters; FFT convolution replaces the reference
  ``lfilter`` FIR loop so it stays cheap on Colab's two CPU cores.
"""
from __future__ import annotations

import io
import warnings
from dataclasses import dataclass

import numpy as np
from scipy import signal as sps

# ---------------------------------------------------------------------------
# Codec round trips
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CodecSpec:
    name: str          # tag used in configs
    encoder: str       # FFmpeg encoder name
    container: str     # FFmpeg muxer name
    rate: int          # sample rate the codec runs at
    bitrates: tuple[int, ...]  # bits/s to choose from; () for fixed-rate PCM codecs
    options: tuple[tuple[str, str], ...] = ()
    priming: int = 0   # encoder delay in samples at ``rate`` that the decoder leaves in


CODECS: dict[str, CodecSpec] = {
    # WhatsApp / Telegram / most VoIP voice notes and calls
    "opus": CodecSpec("opus", "libopus", "ogg", 16000, (8000, 12000, 16000, 24000, 32000),
                      (("application", "voip"),)),
    # Forwarded or downloaded clips, social media
    "mp3": CodecSpec("mp3", "libmp3lame", "mp3", 16000, (24000, 32000, 48000, 64000)),
    "aac": CodecSpec("aac", "aac", "adts", 16000, (24000, 32000, 48000), priming=1024),
    # Landline / PSTN legs: 8 kHz narrowband with logarithmic companding
    "g711_mulaw": CodecSpec("g711_mulaw", "pcm_mulaw", "wav", 8000, ()),
    "g711_alaw": CodecSpec("g711_alaw", "pcm_alaw", "wav", 8000, ()),
}


def available_codecs(requested: list[str] | tuple[str, ...] | None = None) -> list[str]:
    """Codecs from ``requested`` (default: all) that this PyAV build can encode."""
    names = list(requested) if requested else list(CODECS)
    unknown = [n for n in names if n not in CODECS]
    if unknown:
        raise ValueError(f"unknown codec(s) {unknown}; choose from {sorted(CODECS)}")
    try:
        import av
    except ImportError:
        warnings.warn(
            "PyAV is not installed (pip install av); codec augmentation is disabled.",
            stacklevel=2,
        )
        return []
    usable = []
    for name in names:
        try:
            av.codec.Codec(CODECS[name].encoder, "w")
            usable.append(name)
        except Exception:  # noqa: BLE001 - encoder not compiled into this FFmpeg
            warnings.warn(f"codec {name!r} ({CODECS[name].encoder}) is not available in PyAV's "
                          "FFmpeg build; skipping it.", stacklevel=2)
    return usable


def _fit_length(wav: np.ndarray, length: int) -> np.ndarray:
    if len(wav) >= length:
        return wav[:length]
    if len(wav) == 0:
        return np.zeros(length, dtype=np.float32)
    return np.tile(wav, int(np.ceil(length / len(wav))))[:length]


def codec_roundtrip(wav: np.ndarray, sample_rate: int, codec: str, bitrate: int | None = None) -> np.ndarray:
    """Encode and decode ``wav`` through ``codec`` entirely in memory.

    Returns float32 at ``sample_rate`` with the input length (encoder priming and
    padding are trimmed or tiled away).
    """
    import av

    spec = CODECS[codec]
    pcm = np.clip(np.asarray(wav, dtype=np.float32), -1.0, 1.0)
    buffer = io.BytesIO()
    with av.open(buffer, mode="w", format=spec.container) as out:
        stream = out.add_stream(spec.encoder, rate=spec.rate)
        ctx = stream.codec_context
        ctx.layout = "mono"
        if spec.bitrates:
            ctx.bit_rate = int(bitrate or spec.bitrates[0])
        if spec.options:
            ctx.options = dict(spec.options)
        frame = av.AudioFrame.from_ndarray(pcm[None, :], format="flt", layout="mono")
        frame.sample_rate = sample_rate
        resampler = av.AudioResampler(format=ctx.format.name, layout="mono", rate=spec.rate)
        fifo = av.AudioFifo()
        for chunk in resampler.resample(frame) + resampler.resample(None):
            fifo.write(chunk)
        size = ctx.frame_size or 1024
        while fifo.samples >= size:
            for packet in stream.encode(fifo.read(size)):
                out.mux(packet)
        if fifo.samples:
            for packet in stream.encode(fifo.read()):
                out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)

    buffer.seek(0)
    decoded = []
    with av.open(buffer, mode="r") as inp:
        resampler = av.AudioResampler(format="flt", layout="mono", rate=sample_rate)
        for frame in inp.decode(audio=0):
            for chunk in resampler.resample(frame):
                decoded.append(chunk.to_ndarray().reshape(-1))
        for chunk in resampler.resample(None):
            decoded.append(chunk.to_ndarray().reshape(-1))
    out_wav = np.concatenate(decoded) if decoded else np.zeros(0, dtype=np.float32)
    if spec.priming:
        out_wav = out_wav[int(round(spec.priming * sample_rate / spec.rate)):]
    return np.ascontiguousarray(_fit_length(out_wav.astype(np.float32), len(pcm)))


def random_codec(wav: np.ndarray, sample_rate: int, codecs: list[str], nprng: np.random.Generator) -> np.ndarray:
    name = codecs[int(nprng.integers(len(codecs)))]
    spec = CODECS[name]
    bitrate = int(nprng.choice(spec.bitrates)) if spec.bitrates else None
    return codec_roundtrip(wav, sample_rate, name, bitrate)


# ---------------------------------------------------------------------------
# RawBoost
# ---------------------------------------------------------------------------

# Defaults from the paper / reference implementation (algo 1-3 parameters).
RAWBOOST_DEFAULTS = {
    "n_f": 5, "n_bands": 5, "min_f": 20.0, "max_f": 8000.0, "min_bw": 100.0, "max_bw": 1000.0,
    "min_coeff": 10, "max_coeff": 100, "min_g": 0.0, "max_g": 0.0,
    "min_bias_lin_nonlin": 5.0, "max_bias_lin_nonlin": 20.0,
    "p": 10.0, "g_sd": 2.0,
    "snr_min": 10.0, "snr_max": 40.0,
}
RAWBOOST_ALGOS = ("lnl", "isd", "ssi", "lnl_isd")


def _uniform(nprng: np.random.Generator, low: float, high: float) -> float:
    return float(nprng.uniform(low, high)) if high > low else float(low)


def _norm_wav(x: np.ndarray, always: bool) -> np.ndarray:
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak > 0 and (always or peak > 1.0):
        return x / peak
    return x


def _notch_filter(nprng: np.random.Generator, fs: int, n_bands: int, min_f: float, max_f: float,
                  min_bw: float, max_bw: float, min_coeff: int, max_coeff: int,
                  min_g: float, max_g: float) -> np.ndarray:
    """Cascade of random band-pass FIRs (RawBoost genNotchCoeffs)."""
    nyquist = fs / 2.0
    b = np.ones(1)
    for _ in range(n_bands):
        fc = _uniform(nprng, min_f, min(max_f, nyquist))
        bw = _uniform(nprng, min_bw, max_bw)
        taps = int(_uniform(nprng, min_coeff, max_coeff))
        if taps % 2 == 0:
            taps += 1  # firwin band-pass needs an odd tap count
        f1 = max(fc - bw / 2.0, 1e-3)
        f2 = min(fc + bw / 2.0, nyquist - 1e-3)
        if f2 <= f1:
            continue
        b = np.convolve(sps.firwin(taps, [f1, f2], window="hamming", pass_zero=False, fs=fs), b)
    gain_db = _uniform(nprng, min_g, max_g)
    _, response = sps.freqz(b, 1, worN=512, fs=fs)
    peak = float(np.max(np.abs(response))) or 1.0
    return (10.0 ** (gain_db / 20.0)) * b / peak


def _fir(x: np.ndarray, b: np.ndarray) -> np.ndarray:
    return sps.oaconvolve(x, b, mode="same")


def rawboost_lnl(x: np.ndarray, fs: int, nprng: np.random.Generator, cfg: dict) -> np.ndarray:
    """Linear + non-linear convolutive noise: sum of filtered x, x^2, ..., x^n_f."""
    y = np.zeros_like(x, dtype=np.float64)
    min_g, max_g = cfg["min_g"], cfg["max_g"]
    for order in range(cfg["n_f"]):
        if order == 1:  # non-linear components are attenuated relative to the linear one
            min_g -= cfg["min_bias_lin_nonlin"]
            max_g -= cfg["max_bias_lin_nonlin"]
        b = _notch_filter(nprng, fs, cfg["n_bands"], cfg["min_f"], cfg["max_f"], cfg["min_bw"],
                          cfg["max_bw"], cfg["min_coeff"], cfg["max_coeff"], min_g, max_g)
        y += _fir(np.power(x, order + 1), b)
    y -= np.mean(y)
    return _norm_wav(y, always=False)


def rawboost_isd(x: np.ndarray, fs: int, nprng: np.random.Generator, cfg: dict) -> np.ndarray:
    """Impulsive signal-dependent noise on a random P% of samples."""
    beta = _uniform(nprng, 0.0, cfg["p"])
    y = np.array(x, dtype=np.float64, copy=True)
    count = int(len(x) * beta / 100.0)
    if count:
        idx = nprng.permutation(len(x))[:count]
        f_r = (2.0 * nprng.random(count) - 1.0) * (2.0 * nprng.random(count) - 1.0)
        y[idx] = x[idx] + cfg["g_sd"] * x[idx] * f_r
    return _norm_wav(y, always=False)


def rawboost_ssi(x: np.ndarray, fs: int, nprng: np.random.Generator, cfg: dict) -> np.ndarray:
    """Stationary signal-independent (coloured) noise at a random SNR."""
    noise = nprng.normal(0.0, 1.0, len(x))
    b = _notch_filter(nprng, fs, cfg["n_bands"], cfg["min_f"], cfg["max_f"], cfg["min_bw"],
                      cfg["max_bw"], cfg["min_coeff"], cfg["max_coeff"], cfg["min_g"], cfg["max_g"])
    noise = _norm_wav(_fir(noise, b), always=True)
    snr = _uniform(nprng, cfg["snr_min"], cfg["snr_max"])
    signal_norm = float(np.linalg.norm(x, 2))
    noise_norm = float(np.linalg.norm(noise, 2)) or 1.0
    return x + noise / noise_norm * signal_norm / (10.0 ** (0.05 * snr))


def rawboost(x: np.ndarray, fs: int, algo: str, nprng: np.random.Generator,
             overrides: dict | None = None) -> np.ndarray:
    cfg = {**RAWBOOST_DEFAULTS, **(overrides or {})}
    x64 = np.asarray(x, dtype=np.float64)
    if algo == "lnl":
        y = rawboost_lnl(x64, fs, nprng, cfg)
    elif algo == "isd":
        y = rawboost_isd(x64, fs, nprng, cfg)
    elif algo == "ssi":
        y = rawboost_ssi(x64, fs, nprng, cfg)
    elif algo == "lnl_isd":  # the paper's series combination (reference algo 5)
        y = rawboost_isd(rawboost_lnl(x64, fs, nprng, cfg), fs, nprng, cfg)
    else:
        raise ValueError(f"unknown RawBoost algo {algo!r}; choose from {RAWBOOST_ALGOS}")
    y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0)
    # LnL's cascaded band-pass filters leave the clip ~30x quieter. Restore the input
    # level so loudness cannot become a cue for "augmented" (a small, deliberate
    # departure from the reference code, which leaves the level as is).
    in_rms = float(np.sqrt(np.mean(x64 ** 2)))
    out_rms = float(np.sqrt(np.mean(y ** 2)))
    if in_rms > 0 and out_rms > 0:
        y = y * (in_rms / out_rms)
    return np.ascontiguousarray(y, dtype=np.float32)
