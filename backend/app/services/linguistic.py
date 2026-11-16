"""Linguistic risk: multilingual social-engineering lexicons (EN/HI/MR/TA + Hinglish)."""
from __future__ import annotations

import re

LEXICONS: dict[str, list[str]] = {
    "en": [
        "immediately", "urgent", "right away", "don't tell anyone", "do not tell", 
        "transfer now", "transfer immediately", "wire transfer", "otp", "pin", 
        "ceo", "director", "manager", "authorize", "confidential", "secret", "cvv"
    ],
    "hi": [
        "तुरंत", "अभी", "अभी के अभी", "जल्दी", "किसी को मत बताना", "गुप्त", 
        "ट्रांसफर", "ओटीपी", "खाता ब्लॉक", "पैसे भेजो", "अधिकारी", "सीईओ"
    ],
    "mr": [
        "तात्काळ", "लगेच", "गुप्त", "ट्रान्सफर", "पैसे पाठवा", "कोणाला सांगू नका"
    ],
    "ta": [
        "உடனே", "உடனடி", "ரகசியம்", "பரிமாற்றம்", "யாருக்கும் சொல்லாதே"
    ],
    "hinglish": [
        "turant", "abhi ke abhi", "transfer kar", "paise bhej", "otp bata", 
        "secret rakh", "kisi ko mat batana", "ceo bol raha hu", "boss ka order", 
        "emergency hai", "account block", "kyc update kar", "wire bhej"
    ],
}


def score_text(transcript: str) -> tuple[float, list[str]]:
    """Score transcript for linguistic urgency and social engineering cues."""
    t = transcript.lower()
    hits: list[str] = []
    
    for lang, words in LEXICONS.items():
        for w in words:
            # Word boundary or exact substring check
            pattern = rf"(?:\b|\s|^){re.escape(w.lower())}(?:\b|\s|$)"
            if re.search(pattern, t) or w.lower() in t:
                hits.append(w)

    unique_hits = sorted(set(hits))
    if not t.strip():
        return 0.0, []

    if not unique_hits:
        return 0.05, []

    # Calibrated risk: base 0.20 + 0.22 per distinct hit capped at 0.95
    score = min(0.95, 0.20 + 0.22 * len(unique_hits))
    return float(round(score, 3)), unique_hits

