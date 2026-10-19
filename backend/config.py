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
#   LLM_PROVIDER = auto (Groq if GROQ_API_KEY is set, else Claude if ANTHROPIC_API_KEY is set, else rules)
#                | groq | claude | rules
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "12"))

# Voice output. Groq's only voice model is English-only, so Hindi/Hinglish speech uses
# Sarvam AI's Bulbul (Indian voices) when its key is set, else the browser's voice.
#   TTS_PROVIDER = auto | sarvam | browser
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "auto").strip().lower()
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
SARVAM_TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v4-flash")
SARVAM_SPEAKER_HI = os.getenv("SARVAM_SPEAKER_HI", "shubh_enhi_ads")
SARVAM_SPEAKER_EN = os.getenv("SARVAM_SPEAKER_EN", "shubh_en_narration")
SARVAM_PACE = float(os.getenv("SARVAM_PACE", "0.95"))
TTS_CACHE = Path(os.getenv("TTS_CACHE", ROOT / "data" / "tts_cache"))

LANGS = ("hinglish", "hi", "en")
