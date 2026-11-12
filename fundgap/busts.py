"""Bust labels (RULE.md section 2.7).

B1 (primary): the company files an 8-K listing Item 1.03 "Bankruptcy or
Receivership". Source: EDGAR submissions API, which lists every filing with
its 8-K item numbers.

B2 (secondary): B1, OR trailing-four-quarter capex falls to half or less of
its highest value over the previous 12 quarters.
"""

from __future__ import annotations

import pandas as pd

from .config import DATA_RAW
from .edgar import BASE, _headers, cik10, filing_index_url, submissions
from .quarterly import calendar_quarter
from .sources import fetch_json

FILING_COLS = ["accessionNumber", "filingDate", "reportDate", "form", "items"]

# 8-Ks whose EDGAR index metadata lists Item 1.03 but whose document does not
# report a bankruptcy. Each was verified by reading the filing (peer review,
# CHANGELOG v1.3). Results are reported both with and without this correction.
MISTAGGED_1_03 = {
    "0001518909-14-000034": "Black Elk Energy Offshore Operations 8-K of 2014-09-19 reports only "
                            "Items 5.02 and 9.01 (an officer's resignation); no bankruptcy.",
}
APPLY_MISTAG_CORRECTION = True


def all_filings(cik) -> pd.DataFrame:
    """Every filing for a company. The submissions API puts the most recent
    ~1,000 filings in 'recent' and older ones in extra pages listed in 'files'."""
    sub = submissions(cik)
    frames = [pd.DataFrame({c: sub["filings"]["recent"].get(c, []) for c in FILING_COLS})]
    for page in sub["filings"].get("files", []):
        url = f"{BASE}/submissions/{page['name']}"
        path = DATA_RAW / "edgar" / "submissions" / page["name"].replace(".json", ".json.gz")
        older = fetch_json(url, path, headers=_headers())
        frames.append(pd.DataFrame({c: older.get(c, []) for c in FILING_COLS}))
    df = pd.concat(frames, ignore_index=True)
    df["cik"] = int(cik)
    return df


def bankruptcy_events(filings: pd.DataFrame, start="2013-01-01", end="2019-12-31") -> pd.DataFrame:
    """8-K / 8-K/A filings whose item list includes 1.03, within [start, end]."""
    f = filings[filings["form"].isin(["8-K", "8-K/A"])].copy()
    has_103 = [("1.03" in [x.strip() for x in str(items).split(",")]) for items in f["items"].fillna("")]
    f = f[pd.Series(has_103, index=f.index, dtype=bool)]  # stays a table even when empty
    if APPLY_MISTAG_CORRECTION:
        f = f[~f["accessionNumber"].isin(MISTAGGED_1_03)]
    # The event date is the report date if given, else the filing date.
    f["event_date"] = f["reportDate"].where(f["reportDate"].fillna("") != "", f["filingDate"])
    f = f[(f["event_date"] >= start) & (f["event_date"] <= end)].sort_values("event_date")
    f["source_url"] = [filing_index_url(c, a) for c, a in zip(f["cik"], f["accessionNumber"])]
    return f


def last_periodic_filing(filings: pd.DataFrame) -> str | None:
    p = filings[filings["form"].isin(["10-K", "10-Q", "10-K/A", "10-Q/A", "10-KT"])]
    return None if p.empty else p["filingDate"].max()


def capex_cut_quarter(ttm_capex: pd.Series, first="2013Q1", last="2019Q4") -> pd.Period | None:
    """First quarter in [first, last] where TTM capex <= half its highest value
    over the previous 12 quarters (needs at least 4 earlier values)."""
    s = ttm_capex.dropna().sort_index()
    for q, v in s.items():
        if q < pd.Period(first) or q > pd.Period(last):
            continue
        prior = s[(s.index >= q - 12) & (s.index <= q - 1)]
        if len(prior) >= 4 and v <= 0.5 * prior.max():
            return q
    return None


def to_quarter(date_str) -> pd.Period:
    """Plain calendar quarter of an event date (no 52/53-week adjustment:
    that rule is for fiscal period ends, not for events)."""
    return pd.Period(pd.Timestamp(date_str), freq="Q")
