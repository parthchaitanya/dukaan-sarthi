"""Minimal Claude Messages API client (stdlib only, so the demo has no extra dependencies)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import config

API_URL = "https://api.anthropic.com/v1/messages"


class LLMError(RuntimeError):
    pass


def enabled() -> bool:
    return bool(config.ANTHROPIC_API_KEY)


def create(system: str, messages: list, tools: list | None = None, max_tokens: int = 600) -> dict:
    if not enabled():
        raise LLMError("ANTHROPIC_API_KEY is not set")
    body = {"model": config.ANTHROPIC_MODEL, "max_tokens": max_tokens, "system": system, "messages": messages}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        API_URL, data=json.dumps(body).encode(), method="POST",
        headers={"content-type": "application/json", "x-api-key": config.ANTHROPIC_API_KEY,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT_S) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise LLMError(f"Claude API error {e.code}: {e.read()[:300]!r}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise LLMError(f"Claude API unreachable: {e}") from e
