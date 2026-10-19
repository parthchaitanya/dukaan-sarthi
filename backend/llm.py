"""Minimal LLM clients (stdlib only, so the demo has no extra dependencies).

  * Claude: Anthropic Messages API
  * Grok:   xAI's OpenAI-compatible Chat Completions API (https://api.x.ai/v1)
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
    """Which LLM answers open-ended questions: 'claude', 'grok', or None (offline rules)."""
    p = config.LLM_PROVIDER
    if p == "rules":
        return None
    if p == "claude":
        return "claude" if config.ANTHROPIC_API_KEY else None
    if p == "grok":
        return "grok" if config.XAI_API_KEY else None
    if config.ANTHROPIC_API_KEY:
        return "claude"
    if config.XAI_API_KEY:
        return "grok"
    return None


def enabled() -> bool:
    return provider() is not None


def model_name() -> str | None:
    return {"claude": config.ANTHROPIC_MODEL, "grok": config.GROK_MODEL}.get(provider())


def _post(url: str, body: dict, headers: dict, raw: bool = False):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json", **headers})
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


# ---------------------------------------------------------------- Grok (xAI)
def grok_chat(messages: list, tools: list | None = None, max_tokens: int = 600) -> dict:
    """xAI Chat Completions (OpenAI-compatible). `messages` uses OpenAI roles: system/user/assistant/tool."""
    if not config.XAI_API_KEY:
        raise LLMError("XAI_API_KEY is not set")
    body = {"model": config.GROK_MODEL, "messages": messages, "max_tokens": max_tokens}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    if config.GROK_REASONING_EFFORT:
        body["reasoning_effort"] = config.GROK_REASONING_EFFORT
    return _post(config.XAI_BASE_URL.rstrip("/") + "/chat/completions", body,
                 {"authorization": f"Bearer {config.XAI_API_KEY}"})


def grok_tts(text: str, lang: str) -> bytes:
    """xAI text-to-speech: returns MP3 bytes. `lang` is a BCP-47 code ('hi', 'en')."""
    if not config.XAI_API_KEY:
        raise LLMError("XAI_API_KEY is not set")
    body = {"text": text, "language": lang, "voice_id": config.GROK_TTS_VOICE, "speed": config.GROK_TTS_SPEED,
            "output_format": {"codec": "mp3", "sample_rate": 24000, "bit_rate": 128000}}
    return _post(config.XAI_BASE_URL.rstrip("/") + "/tts", body,
                 {"authorization": f"Bearer {config.XAI_API_KEY}"}, raw=True)
