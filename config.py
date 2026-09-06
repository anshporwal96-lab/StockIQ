"""
config.py
=========
One single place that reads every setting from the environment (.env file).

WHY THIS FILE EXISTS
--------------------
If settings were scattered across the code, changing the database or the AI
model would mean hunting through many files. Here, everything lives in one
class. The rest of the app just reads `Config.SOMETHING`.

Nothing secret is hard-coded here - secrets come from the .env file, which is
listed in .gitignore so it never reaches GitHub.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# The folder this file lives in. Used to build absolute paths so the app works
# no matter which directory you run `python app.py` from.
BASE_DIR = Path(__file__).resolve().parent

# load_dotenv() reads the ".env" file and puts each KEY=VALUE line into the
# process environment, so os.getenv() below can find them.
load_dotenv(BASE_DIR / ".env")


def _get_int(name: str, default: int) -> int:
    """Read an integer setting, falling back to `default` if it is missing or
    not a valid number. Keeps a typo in .env from crashing the whole app."""
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Config:
    """All application settings. Read once at startup."""

    # ----- Flask ----------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key-change-me")
    ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = ENV == "development"

    # ----- Database -------------------------------------------------------
    # SQLite by default. To move to PostgreSQL later you only change this one
    # line in .env, e.g.:
    #   DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/stockiq
    # No application code has to change, because we only ever talk to the
    # database through SQLAlchemy.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'stockiq.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Off: it only adds overhead.

    # ----- Sessions / cookies --------------------------------------------
    SESSION_COOKIE_HTTPONLY = True   # JavaScript cannot read the login cookie.
    SESSION_COOKIE_SAMESITE = "Lax"  # Blocks most cross-site request forgery.
    # Only send the cookie over HTTPS in production. Locally we use http://,
    # so this must stay False during development or login would not work.
    SESSION_COOKIE_SECURE = ENV == "production"

    # ----- Data provider --------------------------------------------------
    # "demo"     -> offline, clearly-labelled sample data (default)
    # "yfinance" -> real data, requires `pip install yfinance`
    DATA_PROVIDER = os.getenv("DATA_PROVIDER", "demo").strip().lower()

    # ----- AI -------------------------------------------------------------
    AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic").strip().lower()
    AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
    AI_MODEL = os.getenv("AI_MODEL", "claude-opus-5").strip()

    # ----- News -----------------------------------------------------------
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()

    # ----- Cache lifetimes (seconds) --------------------------------------
    # Documented in the README. Short for prices, long for annual reports.
    CACHE_TTL = {
        "price": _get_int("CACHE_TTL_PRICE", 60),
        "history": _get_int("CACHE_TTL_HISTORY", 900),
        "financials": _get_int("CACHE_TTL_FINANCIALS", 86400),
        "quarterly": _get_int("CACHE_TTL_FINANCIALS", 86400),
        "shareholding": _get_int("CACHE_TTL_FINANCIALS", 86400),
        "news": _get_int("CACHE_TTL_NEWS", 900),
        "company": _get_int("CACHE_TTL_COMPANY", 604800),
        "market": _get_int("CACHE_TTL_PRICE", 60),
        "ai": _get_int("CACHE_TTL_AI", 3600),
    }

    # ----- Rate limiting --------------------------------------------------
    # Simple protection so one visitor cannot hammer the AI endpoint.
    RATE_LIMIT_AI_PER_MINUTE = _get_int("RATE_LIMIT_AI_PER_MINUTE", 12)
    RATE_LIMIT_API_PER_MINUTE = _get_int("RATE_LIMIT_API_PER_MINUTE", 120)

    # ----- Convenience flags ---------------------------------------------
    @classmethod
    def ai_enabled(cls) -> bool:
        """True only when a real AI key is configured. When False the app uses
        a transparent rule-based writer instead, and says so in the UI."""
        return bool(cls.AI_API_KEY)

    @classmethod
    def using_demo_data(cls) -> bool:
        """True when the built-in sample dataset is in use. The UI shows a
        'DEMO DATA' badge whenever this is True."""
        return cls.DATA_PROVIDER == "demo"
