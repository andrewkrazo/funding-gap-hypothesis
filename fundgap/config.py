"""Paths and credentials. Credentials come from environment variables only,
so nothing private is ever written into the repository.

    SEC_USER_AGENT   required by the SEC: "Your Name your@email.com"
    FRED_API_KEY     free key from https://fred.stlouisfed.org/docs/api/api_key.html
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_CLEAN = ROOT / "data" / "clean"
FIGURES = ROOT / "figures"
SOURCES_LOG = DATA_RAW / "SOURCES.csv"


def _require(name: str, help_text: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set. {help_text}")
    return value


def sec_user_agent() -> str:
    return _require("SEC_USER_AGENT",
                    'Set it to "Your Name your@email.com" (the SEC requires this).')


def fred_api_key() -> str:
    return _require("FRED_API_KEY", "Get a free key at fred.stlouisfed.org.")
