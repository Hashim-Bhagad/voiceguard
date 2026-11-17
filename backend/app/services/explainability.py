"""Explainability Engine for VoiceGuard.
Extracts acoustic forensic markers (pitch micro-jitter, spectral discontinuity at 3-4kHz, prosody dynamics)
and categorizes linguistic social-engineering triggers into actionable, explainable telemetry.
"""
from __future__ import annotations

import logging
from typing import Any
import numpy as np

from app.services import linguistic

log = logging.getLogger("voiceguard.explainability")

# Categories come from the lexicon itself (linguistic.LEXICON), so every flagged
# term has the category it was written with.


def extract_pitch_jitter(audio_16k: np.ndarray, sample_rate: int = 16000) -> float:
    """Estimate pitch period perturbation (micro-jitter) percentage.
    Natural human vocal folds exhibit cycle-to-cycle perturbation (~0.8% - 1.8%).
    Synthetic TTS and voice clones often exhibit unnaturally uniform pitch trajectories (<0.40%).
    """
    if audio_16k.size < sample_rate // 2:
        return 0.95  # Not enough samples; default to nominal natural value

    waveform = audio_16k.astype(np.float64)
    # Energy gate: only analyze voiced portions
    frame_len = int(0.03 * sample_rate)  # 30ms frames
    hop_len = int(0.015 * sample_rate)   # 15ms hop

    pitch_periods = []
    num_frames = (len(waveform) - frame_len) // hop_len
    
    for i in range(num_frames):
        frame = waveform[i * hop_len : i * hop_len + frame_len]
        energy = np.mean(frame ** 2)
        if energy < 0.001:
            continue

        # Simplified autocorrelation for pitch detection in speech range [75Hz, 350Hz]
        min_lag = int(sample_rate / 350)  # ~45 samples
        max_lag = int(sample_rate / 75)   # ~213 samples

        corr = np.correlate(frame, frame, mode='full')
        corr = corr[len(corr) // 2 :]
        if max_lag < len(corr):
            peak_lag = min_lag + np.argmax(corr[min_lag:max_lag])
            pitch_periods.append(peak_lag)

    if len(pitch_periods) < 5:
        return 0.85

    periods = np.array(pitch_periods, dtype=np.float64)
    # Relative average perturbation (jitter %)
    diffs = np.abs(np.diff(periods))
    mean_period = np.mean(periods)
    if mean_period <= 0:
        return 0.85

    jitter_pct = (np.mean(diffs) / mean_period) * 100.0
    return float(np.clip(jitter_pct, 0.05, 4.0))


def extract_spectral_discontinuity(audio_16k: np.ndarray, sample_rate: int = 16000) -> float:
    """Measure spectral discontinuity index around 3.0 kHz - 4.5 kHz.
    Neural vocoders (HiFi-GAN, MelGAN, WaveGlow) frequently leave upsampling phase artifacts,
    unnatural energy nulls, or boundary discontinuities in this frequency range.
    Returns an index in [0, 1] where >0.4 indicates anomalous spectral behavior.
    """
    if audio_16k.size < 4000:
        return 0.15

    waveform = audio_16k.astype(np.float64)
    n_fft = 1024
    if len(waveform) < n_fft:
        return 0.15

    # Compute FFT on center segment
    center = len(waveform) // 2
    segment = waveform[max(0, center - n_fft // 2) : min(len(waveform), center + n_fft // 2)]
    if len(segment) < n_fft:
        segment = np.pad(segment, (0, n_fft - len(segment)))

    # Windowing
    window = np.hanning(len(segment))
    spectrum = np.abs(np.fft.rfft(segment * window))
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)

    # Band of interest: 3000 Hz to 4500 Hz
    band_mask = (freqs >= 3000) & (freqs <= 4500)
    baseline_mask = (freqs >= 500) & (freqs <= 2500)

    band_energy = np.mean(spectrum[band_mask] ** 2) if np.any(band_mask) else 1e-6
    baseline_energy = np.mean(spectrum[baseline_mask] ** 2) if np.any(baseline_mask) else 1e-6

    # Measure high-frequency gradient anomaly
    diff_spectrum = np.abs(np.diff(spectrum[band_mask])) if np.any(band_mask) else np.array([0.0])
    roughness = float(np.std(diff_spectrum) / (np.mean(diff_spectrum) + 1e-6))

    ratio = band_energy / (baseline_energy + 1e-6)
    # Combine roughness and band ratio into normalized discontinuity index
    disc_index = float(np.clip(0.15 + (roughness * 0.1) + min(0.4, ratio * 0.5), 0.05, 0.95))
    return round(disc_index, 3)


def categorize_linguistic_hits(hits: list[str]) -> list[dict[str, str]]:
    """Categorize matched keywords into explainable fraud/coercion markers."""
    categorized = []
    seen = set()
    for hit in hits:
        key = hit.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        category = linguistic.category_of(hit)
        categorized.append({
            "keyword": hit,
            "category": category,
            "description": f"Triggered by '{hit}' ({category})",
        })
    return categorized


def generate_forensic_report(
    audio_16k: np.ndarray,
    linguistic_hits: list[str],
    spoof_score: float,
    prosody_flag: str = "normal",
) -> dict[str, Any]:
    """Compile forensic diagnostic telemetry for the Explainable Risk Score (USP 3)."""
    has_audio = audio_16k is not None and audio_16k.size > 0
    jitter = extract_pitch_jitter(audio_16k) if has_audio else 1.0
    spec_disc = extract_spectral_discontinuity(audio_16k) if has_audio else 0.15
    categorized_hits = categorize_linguistic_hits(linguistic_hits)

    diagnostic_reasons = []

    # Acoustic reasons
    if spoof_score >= 0.55:
        diagnostic_reasons.append(
            f"Acoustic model detected synthetic voice synthesis artifacts (confidence: {int(spoof_score*100)}%)"
        )
    elif spoof_score >= 0.35:
        diagnostic_reasons.append(
            f"Acoustic model detected anomalous spectral patterns (confidence: {int(spoof_score*100)}%)"
        )

    # --- markers below are gated by measured reliability -------------------
    # scripts/audit_explainability.py, 50 bona-fide vs 50 spoof clips from the
    # held-out test split. Any claim that fires equally on both classes is not
    # evidence, and printing it as forensic reasoning misleads a reviewer.
    #
    #   jitter_pct              AUC 0.06  -- 94% of genuine and 98% of spoof
    #                                        clips pin at the estimator's 4.0
    #                                        ceiling, so it carries no signal
    #   spectral_discontinuity  AUC 0.60  -- weak
    #   prosody flat rate       40% genuine vs 38% spoof -- no signal
    #   spoof_score (model)     AUC 0.82  -- the only reliable marker
    jitter_saturated = jitter >= 3.99 or jitter <= 0.06

    if jitter_saturated:
        pass  # estimator pinned at a clip bound: report the number, claim nothing
    elif jitter < 0.35:
        diagnostic_reasons.append(
            f"Unnatural pitch micro-jitter detected ({jitter:.2f}% vs expected natural range "
            f"0.8–1.8%): may indicate algorithmic voice synthesis (weak marker, not validated)"
        )
    elif jitter > 2.8:
        diagnostic_reasons.append(
            f"Elevated pitch instability ({jitter:.2f}%) (weak marker, not validated)"
        )

    if spec_disc >= 0.40:
        diagnostic_reasons.append(
            f"Spectral energy anomaly in the 3.2–4.2 kHz band (index: {spec_disc:.2f}). "
            "Weak marker: on the held-out test split this fires on 22% of genuine and 30% of "
            "synthetic clips, so it corroborates at best and cannot stand alone."
        )

    # Prosody flatness fires slightly MORE on genuine speech than on spoof in our
    # measurements, so it must not be presented as evidence of synthesis.
    if prosody_flag == "flat":
        diagnostic_reasons.append(
            "Observation only: low prosodic variation. This does NOT indicate synthesis "
            "(measured 40% of genuine vs 38% of synthetic clips)."
        )

    # Linguistic reasons
    for item in categorized_hits:
        diagnostic_reasons.append(
            f"Social-engineering indicator [{item['category']}]: '{item['keyword']}'"
        )

    if not diagnostic_reasons:
        diagnostic_reasons.append("Speech features consistent with natural human vocal tract; no coercion markers detected.")

    return {
        "jitter_pct": round(jitter, 3),
        "jitter_verdict": (
            "unreliable_estimator_saturated" if jitter_saturated
            else "synthetic_uniform" if jitter < 0.35
            else "natural_human" if jitter <= 2.2
            else "irregular"
        ),
        "spectral_discontinuity": spec_disc,
        "spectral_verdict": "anomalous_band_energy" if spec_disc >= 0.40 else "within_normal_range",
        "prosody_flatness": prosody_flag,
        "threat_categories": categorized_hits,
        "diagnostic_reasons": diagnostic_reasons,
        # Be explicit about what actually carries the decision, so a reviewer does
        # not read four sentences and assume four independent lines of evidence.
        "primary_evidence": "acoustic_model" if spoof_score >= 0.35 else "none",
        "marker_reliability": {
            "acoustic_model": {"auc": 0.82, "usable": True},
            "jitter_pct": {"auc": 0.06, "usable": False, "note": "estimator saturates at 4.0"},
            "spectral_discontinuity": {"auc": 0.60, "usable": False, "note": "weak"},
            "prosody_flatness": {"auc": 0.51, "usable": False, "note": "fires equally on genuine"},
        },
        "measured_on": "50 bona-fide vs 50 spoof clips, held-out test split (English)",
    }
