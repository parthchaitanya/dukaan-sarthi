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

# LLM. Without a key the app uses its built-in rule-based router, so the demo never breaks.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "12"))

LANGS = ("hinglish", "hi", "en")
