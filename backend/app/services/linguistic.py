"""Linguistic risk: multilingual urgency lexicons (EN/HI/MR/TA + Hinglish). Rule-based Day 2."""
import re

LEXICONS: dict[str, list[str]] = {
    "en": ["immediately", "urgent", "don't tell anyone", "do not tell", "transfer now", "otp", "pin", "ceo", "authorize", "secret"],
    "hi": ["तुरंत", "अभी", "किसी को मत बताना", "गुप्त", "ट्रांसफर", "ओटीपी"],
    "mr": ["तात्काळ", "लगेच", "गुप्त", "ट्रान्सफर"],
    "ta": ["உடனே", "உடனடி", "ரகசியம்", "பரிமாற்றம்"],
    "hinglish": ["turant", "abhi", "transfer kar", "otp bata", "secret rakh"],
}

_traCache: str = ""


def score_text(transcript: str) -> tuple[float, list[str]]:
    t = transcript.lower()
    hits: list[str] = []
    for lang, words in LEXICONS.items():
        for w in words:
            if w.lower() in t:
                hits.append(w)
    if not t.strip():
        return 0.0, []
    # 0.25 per unique hit capped at 0.95; TODO: upgrade to MuRIL-tiny classifier.
    score = min(0.95, 0.1 + 0.25 * len(set(hits)))
    if not hits:
        score = 0.05
    return float(score), sorted(set(hits))
