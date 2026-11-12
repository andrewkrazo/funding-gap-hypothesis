"""Reproduce everything, from raw downloads to results, with one command:

    python run_all.py

Needs two environment variables (see README):
    SEC_USER_AGENT   "Your Name your@email.com"  (the SEC requires it)
    FRED_API_KEY     a free key from fred.stlouisfed.org

Raw downloads are cached in data/raw/. Anything already cached is reused;
anything missing is downloaded. Restricted series (Moody's, ICE) are always
re-downloaded locally because they are not redistributed in this repository.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ("Unit tests", [sys.executable, "-m", "pytest", "-q"]),
    ("Stage 1: five large tech spenders (descriptive)", [sys.executable, "stages/stage1_hyperscalers.py"]),
    ("Stage 2A: universe, tags, TTM tables", [sys.executable, "stages/stage2a_universe_and_tags.py"]),
    ("Stage 2B: bankruptcy labels and the test", [sys.executable, "stages/stage2b_test.py"]),
]

for title, cmd in STEPS:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}", flush=True)
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f"Stopped: '{title}' failed (exit code {result.returncode}).")
print("\nDone. See RESULTS.md, figures/ and data/clean/.")
