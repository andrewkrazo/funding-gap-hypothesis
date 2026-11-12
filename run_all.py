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
    # Addendum A1 (RULE.md section 6). The first run looks up ~2,200 SIC codes
    # (about 15 minutes); the result is cached in data/clean/comparison_sic_map.csv.
    ("Addendum A1: pick the comparison boom", [sys.executable, "stages/stage2c_select_comparison.py"]),
    ("Addendum A1: comparison part A (SIC 7370)", [sys.executable, "stages/stage2a_universe_and_tags.py", "7370", "comparison"]),
    ("Addendum A1: comparison part B", [sys.executable, "stages/stage2b_test.py", "comparison"]),
    # Addendum A2 (RULE.md section 7). First run downloads ~4,400 filings (about an hour);
    # the sentences are cached in data/raw/edgar/borrowing_base_sentences.jsonl.gz.
    ("Addendum A2: borrowing-base cuts", [sys.executable, "stages/stage3a_borrowing_base.py"]),
    ("Addendum A2: firm-level lender test", [sys.executable, "stages/stage3b_test.py"]),
    # Audit (CHANGELOG v1.6): recompute using the hand-judged review sheet in data/clean.
    ("Audit: only hand-verified bank cuts", [sys.executable, "stages/stage3c_signal_cut_review.py", "results"]),
]

for title, cmd in STEPS:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}", flush=True)
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(f"Stopped: '{title}' failed (exit code {result.returncode}).")
print("\nDone. See RESULTS.md, figures/ and data/clean/.")
