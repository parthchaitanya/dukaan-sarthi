"""Server-side neural voice (Grok TTS) with a disk cache.

The cache means each sentence is generated once; after one rehearsal the demo's audio
plays from disk even with no internet. Warm it up before presenting:

    python -m backend.tts warm
"""
from __future__ import annotations

import hashlib
import sys

from . import config, llm


def provider() -> str:
    p = config.TTS_PROVIDER
    if p == "browser":
        return "browser"
    if p in ("grok", "auto") and config.XAI_API_KEY:
        return "grok"
    return "browser"


def _path(text: str, lang: str):
    key = hashlib.sha1(f"{config.GROK_TTS_VOICE}|{config.GROK_TTS_SPEED}|{lang}|{text}".encode()).hexdigest()
    return config.TTS_CACHE / f"{key}.mp3"


def audio(text: str, lang: str) -> bytes | None:
    """MP3 for `text`, or None when server voice is off (the browser voice is used instead)."""
    if provider() != "grok":
        return None
    text = text.strip()[:2000]
    if not text:
        return None
    f = _path(text, lang)
    if f.exists():
        return f.read_bytes()
    data = llm.grok_tts(text, "en" if lang == "en" else "hi")
    config.TTS_CACHE.mkdir(parents=True, exist_ok=True)
    f.write_bytes(data)
    return data


def warm(mid: str = "m1") -> int:
    """Pre-generate the audio the demo script plays."""
    import warnings
    warnings.filterwarnings("ignore")
    from .features import ask, brief
    from .i18n import tr_suggestions
    n = 0
    for lang in ("hinglish", "hi", "en"):
        b = brief.brief(mid, lang)
        for line in b["speak_lines"]:
            audio(line, b["speak_lang"]); n += 1
        for q in tr_suggestions(lang):
            r = ask.ask(mid, q, lang)
            audio(r["speak"], r["speak_lang"]); n += 1
    return n


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "warm":
        if provider() != "grok":
            sys.exit("Set XAI_API_KEY (and TTS_PROVIDER=grok or auto) first.")
        print(f"Cached {warm()} clips in {config.TTS_CACHE}")
