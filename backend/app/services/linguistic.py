"""Linguistic risk: multilingual social-engineering lexicons (EN/HI/MR/TA + Hinglish).

Every term carries its category here, in one place, so the score and the
explanation can never disagree about why a phrase was flagged.
"""
from __future__ import annotations

import re

URGENCY = "Urgency"
SECRECY = "Secrecy Isolation"
MONEY = "Financial Coercion"
AUTHORITY = "Executive Impersonation"

LEXICON: dict[str, dict[str, str]] = {
    "en": {
        "immediately": URGENCY, "urgent": URGENCY, "right away": URGENCY,
        "don't tell anyone": SECRECY, "do not tell": SECRECY, "confidential": SECRECY, "secret": SECRECY,
        "transfer now": MONEY, "transfer immediately": MONEY, "wire transfer": MONEY,
        "otp": MONEY, "pin": MONEY, "cvv": MONEY,
        "ceo": AUTHORITY, "director": AUTHORITY, "manager": AUTHORITY, "authorize": AUTHORITY,
    },
    "hi": {
        "तुरंत": URGENCY, "अभी": URGENCY, "अभी के अभी": URGENCY, "जल्दी": URGENCY,
        "किसी को मत बताना": SECRECY, "गुप्त": SECRECY,
        "ट्रांसफर": MONEY, "ओटीपी": MONEY, "खाता ब्लॉक": MONEY, "पैसे भेजो": MONEY,
        "अधिकारी": AUTHORITY, "सीईओ": AUTHORITY,
    },
    "mr": {
        "तात्काळ": URGENCY, "लगेच": URGENCY,
        "गुप्त": SECRECY, "कोणाला सांगू नका": SECRECY,
        "ट्रान्सफर": MONEY, "पैसे पाठवा": MONEY,
    },
    "ta": {
        "உடனே": URGENCY, "உடனடி": URGENCY,
        "ரகசியம்": SECRECY, "யாருக்கும் சொல்லாதே": SECRECY,
        "பரிமாற்றம்": MONEY,
    },
    "hinglish": {
        "turant": URGENCY, "abhi ke abhi": URGENCY, "emergency hai": URGENCY,
        "secret rakh": SECRECY, "kisi ko mat batana": SECRECY,
        "transfer kar": MONEY, "paise bhej": MONEY, "otp bata": MONEY, "account block": MONEY,
        "kyc update kar": MONEY, "wire bhej": MONEY,
        "ceo bol raha hu": AUTHORITY, "boss ka order": AUTHORITY,
    },
}

# Backwards-compatible view: language -> list of terms.
LEXICONS: dict[str, list[str]] = {lang: list(terms) for lang, terms in LEXICON.items()}

CATEGORY_OF: dict[str, str] = {
    term.lower(): category for terms in LEXICON.values() for term, category in terms.items()
}


def _matches(term: str, text: str) -> bool:
    """Latin-script terms match whole words only ("pin" must not match "spinning").

    Indic scripts keep a substring match: Python's \\b treats combining vowel signs
    as non-word characters, so a boundary check would split words in the middle.
    """
    if term.isascii():
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
    return term in text


def score_text(transcript: str) -> tuple[float, list[str]]:
    """Score transcript for linguistic urgency and social engineering cues."""
    t = transcript.lower()
    if not t.strip():
        return 0.0, []

    found = {term for term in CATEGORY_OF if _matches(term, t)}
    # A term inside a longer matched phrase is the same cue, not a second one:
    # "secret rakh" counts once, not as "secret" + "secret rakh".
    unique_hits = sorted(h for h in found if not any(h != other and h in other for other in found))

    if not unique_hits:
        return 0.05, []

    # Calibrated risk: base 0.20 + 0.22 per distinct hit capped at 0.95
    score = min(0.95, 0.20 + 0.22 * len(unique_hits))
    return float(round(score, 3)), unique_hits


def category_of(term: str) -> str:
    return CATEGORY_OF.get(term.lower().strip(), "General Fraud Indicator")
