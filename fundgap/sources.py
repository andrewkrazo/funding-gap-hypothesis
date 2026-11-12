"""Download helper that caches every raw response and logs where it came from.

Every file in data/raw/ has a row in data/raw/SOURCES.csv with the exact URL,
the time it was retrieved (UTC), and a SHA-256 fingerprint of the bytes. That
is how any number in this project can be traced back to its source.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .config import ROOT, SOURCES_LOG

_last_request = 0.0


def fetch_json(url: str, local_path: Path, headers=None,
               min_interval: float = 0.15, redact: str | None = None) -> dict:
    """Return parsed JSON for `url`, downloading only if not cached already.

    The raw bytes are saved gzip-compressed at `local_path` (ending .json.gz).
    `redact` is a secret (like an API key) to strip from the URL in the log.
    The SEC asks for at most 10 requests per second; min_interval keeps us
    well under that. `headers` may be a function: it is only called when a
    download is actually needed, so reading cached files never asks for
    credentials (e.g. the SEC User-Agent).
    """
    global _last_request
    local_path = Path(local_path)
    if local_path.exists():
        with gzip.open(local_path, "rb") as f:
            return json.loads(f.read())

    if callable(headers):
        headers = headers()
    wait = min_interval - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    resp = requests.get(url, headers=headers or {}, timeout=60)
    _last_request = time.time()
    if resp.status_code != 200:
        # Never guess or fill in: stop and report.
        raise RuntimeError(f"Download failed ({resp.status_code}) for {url}")

    raw = resp.content
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(local_path, "wb") as f:
        f.write(raw)

    logged_url = url.replace(redact, "REDACTED") if redact else url
    _log_source(logged_url, local_path, raw)
    return json.loads(raw)


def fetch_text(url: str, local_path: Path, headers: dict | None = None,
               min_interval: float = 0.15) -> str:
    """Like fetch_json, for non-JSON responses (e.g. EDGAR's Atom listings)."""
    global _last_request
    local_path = Path(local_path)
    if local_path.exists():
        with gzip.open(local_path, "rb") as f:
            return f.read().decode("latin-1")
    wait = min_interval - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    resp = requests.get(url, headers=headers or {}, timeout=60)
    _last_request = time.time()
    if resp.status_code != 200:
        raise RuntimeError(f"Download failed ({resp.status_code}) for {url}")
    raw = resp.content
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(local_path, "wb") as f:
        f.write(raw)
    _log_source(url, local_path, raw)
    return raw.decode("latin-1")


def _log_source(url: str, local_path: Path, raw: bytes) -> None:
    SOURCES_LOG.parent.mkdir(parents=True, exist_ok=True)
    new_file = not SOURCES_LOG.exists()
    with open(SOURCES_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["url", "retrieved_utc", "local_file", "sha256_of_raw_bytes"])
        w.writerow([url,
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    local_path.relative_to(ROOT).as_posix(),
                    hashlib.sha256(raw).hexdigest()])
