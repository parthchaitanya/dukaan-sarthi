"""Central configuration. Everything can be overridden with environment variables."""
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Load a local .env file if present (KEY=VALUE lines); real environment variables win.
_env = ROOT / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        if "=" in _line and not _line.lstrip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())
DB_PATH = Path(os.getenv("DUKAAN_DB", ROOT / "data" / "dukaan.db"))
METRICS_CACHE = Path(os.getenv("DUKAAN_METRICS_CACHE", ROOT / "data" / "metrics.json"))
FRONTEND_DIST = ROOT / "frontend" / "dist"

# The demo runs on a fixed "today" so the story is the same every time you present.
DEMO_TODAY = date.fromisoformat(os.getenv("DEMO_TODAY", "2026-10-20"))
HISTORY_DAYS = int(os.getenv("HISTORY_DAYS", "183"))  # ~6 months
SEED = int(os.getenv("SEED", "42"))

# LLM for open-ended Ask Anything questions. Without any key the built-in rule-based
# router answers, so the demo never breaks.
#   LLM_PROVIDER = auto (Claude if its key is set, else Grok if its key is set, else rules)
#                | claude | grok | rules
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
XAI_API_KEY = os.getenv("XAI_API_KEY", "").strip()
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
GROK_MODEL = os.getenv("GROK_MODEL", "grok-4.3")
GROK_REASONING_EFFORT = os.getenv("GROK_REASONING_EFFORT", "").strip()  # none|low|medium|high; empty = model default
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "12"))

# Voice output.
#   TTS_PROVIDER = auto (Grok voice if XAI_API_KEY is set, else the browser's voice) | grok | browser
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "auto").strip().lower()
GROK_TTS_VOICE = os.getenv("GROK_TTS_VOICE", "eve")
GROK_TTS_SPEED = float(os.getenv("GROK_TTS_SPEED", "0.95"))
TTS_CACHE = Path(os.getenv("TTS_CACHE", ROOT / "data" / "tts_cache"))

LANGS = ("hinglish", "hi", "en")
