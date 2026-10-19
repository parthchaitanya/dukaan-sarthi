"""Make text sound right when spoken.

Screen text is written for reading ("₹1,95,665", "2.1x", "C-77B16", "9am se 11am").
Text-to-speech engines mangle those, and a Hindi voice reading Latin-script Hinglish
mispronounces many words. This module turns display text into speakable text:

  * Hinglish is *spoken* from the Hindi (Devanagari) version of the same sentence, which
    Hindi voices pronounce correctly; the screen still shows Hinglish.
  * Rupee amounts become words the voice can say ("1 लाख 95 हज़ार 665 रुपये").
  * Symbols and codes are spelled out or replaced (x -> गुना, % -> प्रतिशत, C-77B16 -> एक ग्राहक).
"""
from __future__ import annotations

import re

SPEECH_LANG = {"hinglish": "hi", "hi": "hi", "en": "en"}

_WORDS = {
    "hi": {"rupees": "रुपये", "lakh": "लाख", "crore": "करोड़", "thousand": "हज़ार", "x": "गुना", "pct": "प्रतिशत",
           "customer": "एक ग्राहक", "minus": "माइनस", "out_of": "में से"},
    "en": {"rupees": "rupees", "lakh": "lakh", "crore": "crore", "thousand": "thousand", "x": "times", "pct": "percent",
           "customer": "a customer", "minus": "minus", "out_of": "out of"},
}

_EN_REPL = [
    (r"\bJan\b", "January"), (r"\bFeb\b", "February"), (r"\bMar\b", "March"), (r"\bApr\b", "April"),
    (r"\bJun\b", "June"), (r"\bJul\b", "July"), (r"\bAug\b", "August"), (r"\bSep\b", "September"),
    (r"\bOct\b", "October"), (r"\bNov\b", "November"), (r"\bDec\b", "December"),
    (r"(\d{1,2})am\b", r"\1 a.m."), (r"(\d{1,2})pm\b", r"\1 p.m."), (r"–", " to "),
]
_HI_REPL = [
    (r"\bPaytm\b", "पेटीएम"), (r"\bUPI\b", "यू पी आई"), (r"\bWhatsApp\b", "व्हाट्सऐप"), (r"\bSMS\b", "एस एम एस"),
    (r"\bBP\b", "बी पी"), (r"\bloan\b", "लोन"), (r"\bSarthi\b", "सारथी"), (r"\bDukaan\b", "दुकान"),
    (r"(\d{1,2})am\b", r"सुबह \1 बजे"), (r"(\d{1,2})pm\b", r"\1 बजे"),
]


def _amount_words(n: int, lang: str) -> str:
    """Indian grouping in words: 195665 -> '1 लाख 95 हज़ार 665'. Digits stay digits; voices read those well."""
    w = _WORDS[lang]
    parts = []
    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, rest = divmod(n, 1000)
    if crore:
        parts.append(f"{crore} {w['crore']}")
    if lakh:
        parts.append(f"{lakh} {w['lakh']}")
    if thousand:
        parts.append(f"{thousand} {w['thousand']}")
    if rest or not parts:
        parts.append(str(rest))
    return " ".join(parts)


def speakable(text: str, lang: str) -> str:
    """Display text -> text a TTS voice reads clearly. `lang` is the voice language ('hi' or 'en')."""
    lang = SPEECH_LANG.get(lang, lang)
    w = _WORDS[lang]
    s = text
    s = re.sub(r",?\s?\bC-[0-9A-F]{5}\b", "", s)  # pseudonymous IDs mean nothing when heard
    s = re.sub(r"[🙏✓→•]", "", s)
    # ₹27.5 hazaar / ₹1.2 lakh -> "27 हज़ार 500 रुपये": voices stumble on decimals ("27 दशमलव 5")
    unit = {"lakh": 100_000, "लाख": 100_000, "hazaar": 1000, "हज़ार": 1000, "crore": 10_000_000, "करोड़": 10_000_000}
    s = re.sub(r"[−-]?₹\s?(\d+(?:\.\d+)?)\s*(lakh|लाख|hazaar|हज़ार|crore|करोड़)",
               lambda m: _amount_words(int(round(float(m.group(1)) * unit[m.group(2)] / 100) * 100), lang)
               + " " + w["rupees"], s)
    # ₹1,95,665 -> "1 लाख 95 हज़ार 665 रुपये"
    s = re.sub(r"([−-])?₹\s?([\d,]+)(?:\.\d+)?",
               lambda m: (w["minus"] + " " if m.group(1) else "") + _amount_words(int(m.group(2).replace(",", "")), lang)
               + " " + w["rupees"], s)
    s = re.sub(r"(\d+(?:\.\d+)?)x\b", lambda m: f"{m.group(1)} {w['x']}", s)
    s = re.sub(r"(\d+(?:\.\d+)?)\s?%", lambda m: f"{m.group(1)} {w['pct']}", s)
    s = re.sub(r"(\d+)/100\b", lambda m: f"100 {w['out_of']} {m.group(1)}" if lang == "hi" else f"{m.group(1)} out of 100", s)
    s = re.sub(r"(\d+)\+", r"\1", s)
    for pat, rep in (_HI_REPL if lang == "hi" else _EN_REPL):
        s = re.sub(pat, rep, s)
    s = re.sub(r"^\s*\d+\.\s+", "", s)  # list numbering "1. " at the start of a line
    s = re.sub(r"\s+([,.।])", r"\1", s)
    s = re.sub(r"([,.])\1+", r"\1", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def split_sentences(text: str, max_len: int = 180) -> list[str]:
    """Short chunks: browsers cut off or slur long utterances."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?।])\s+", text) if p.strip()]
    out = []
    for p in parts:
        while len(p) > max_len:
            cut = p.rfind(",", 0, max_len)
            cut = cut if cut > 40 else p.rfind(" ", 0, max_len)
            out.append(p[:cut + 1].strip())
            p = p[cut + 1:].strip()
        out.append(p)
    return out
