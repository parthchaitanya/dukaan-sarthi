"""Minimal LLM clients (stdlib only, so the demo has no extra dependencies).

  * Groq:   OpenAI-compatible Chat Completions (https://api.groq.com/openai/v1), e.g. Llama 3.3 70B
  * Claude: Anthropic Messages API
  * Sarvam: Bulbul text-to-speech (Hindi, Hinglish and Indian English voices)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import config

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class LLMError(RuntimeError):
    pass


def provider() -> str | None:
    """Which LLM answers open-ended questions: 'groq', 'claude', or None (offline rules)."""
    p = config.LLM_PROVIDER
    if p == "rules":
        return None
    if p == "groq":
        return "groq" if config.GROQ_API_KEY else None
    if p == "claude":
        return "claude" if config.ANTHROPIC_API_KEY else None
    if config.GROQ_API_KEY:
        return "groq"
    if config.ANTHROPIC_API_KEY:
        return "claude"
    return None


def enabled() -> bool:
    return provider() is not None


def model_name() -> str | None:
    return {"claude": config.ANTHROPIC_MODEL, "groq": config.GROQ_MODEL}.get(provider())


def _post(url: str, body: dict, headers: dict, raw: bool = False):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json",
                                          # Groq sits behind Cloudflare, which rejects Python's default user agent
                                          "user-agent": "dukaan-sarthi/1.0", **headers})
    try:
        with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT_S) as r:
            data = r.read()
            return data if raw else json.loads(data)
    except urllib.error.HTTPError as e:
        raise LLMError(f"API error {e.code}: {e.read()[:300]!r}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise LLMError(f"API unreachable: {e}") from e


# ---------------------------------------------------------------- Claude
def create(system: str, messages: list, tools: list | None = None, max_tokens: int = 600) -> dict:
    """Anthropic Messages API call."""
    if not config.ANTHROPIC_API_KEY:
        raise LLMError("ANTHROPIC_API_KEY is not set")
    body = {"model": config.ANTHROPIC_MODEL, "max_tokens": max_tokens, "system": system, "messages": messages}
    if tools:
        body["tools"] = tools
    return _post(ANTHROPIC_URL, body, {"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"})


# ---------------------------------------------------------------- Groq
def groq_chat(messages: list, tools: list | None = None, max_tokens: int = 700) -> dict:
    """Groq Chat Completions (OpenAI-compatible). `messages` uses OpenAI roles: system/user/assistant/tool."""
    if not config.GROQ_API_KEY:
        raise LLMError("GROQ_API_KEY is not set")
    body = {"model": config.GROQ_MODEL, "messages": messages, "max_tokens": max_tokens, "temperature": 0.2}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    return _post(config.GROQ_BASE_URL.rstrip("/") + "/chat/completions", body,
                 {"authorization": f"Bearer {config.GROQ_API_KEY}"})


# ---------------------------------------------------------------- Sarvam (voice)
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"


def sarvam_tts(text: str, lang: str) -> bytes:
    """Sarvam Bulbul text-to-speech -> MP3 bytes. `lang` is 'hi' or 'en'."""
    import base64
    if not config.SARVAM_API_KEY:
        raise LLMError("SARVAM_API_KEY is not set")
    body = {"text": text, "language_code": "en-IN" if lang == "en" else "hi-IN",
            "model": config.SARVAM_TTS_MODEL,
            "speaker": config.SARVAM_SPEAKER_EN if lang == "en" else config.SARVAM_SPEAKER_HI,
            "pace": config.SARVAM_PACE, "speech_sample_rate": 24000, "output_audio_codec": "mp3"}
    data = _post(SARVAM_TTS_URL, body, {"api-subscription-key": config.SARVAM_API_KEY})
    audios = data.get("audios") or []
    if not audios:
        raise LLMError(f"Sarvam returned no audio: {str(data)[:200]}")
    return b"".join(base64.b64decode(a) for a in audios)
