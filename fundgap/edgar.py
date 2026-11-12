"""SEC EDGAR access: XBRL company facts, filing lists, and cross-company frames.

API documentation: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from .config import DATA_RAW, sec_user_agent
from .sources import fetch_json

BASE = "https://data.sec.gov"


def _headers() -> dict:
    return {"User-Agent": sec_user_agent(), "Accept-Encoding": "gzip, deflate"}


def cik10(cik: int | str) -> str:
    return str(int(cik)).zfill(10)


@lru_cache(maxsize=None)
def _companyfacts_cached(cik10_str: str) -> dict:
    url = f"{BASE}/api/xbrl/companyfacts/CIK{cik10_str}.json"
    path = DATA_RAW / "edgar" / "companyfacts" / f"CIK{cik10_str}.json.gz"
    return fetch_json(url, path, headers=_headers)


def companyfacts(cik) -> dict:
    """XBRL facts for one company (downloaded once, then cached in memory)."""
    return _companyfacts_cached(cik10(cik))


def submissions(cik) -> dict:
    url = f"{BASE}/submissions/CIK{cik10(cik)}.json"
    path = DATA_RAW / "edgar" / "submissions" / f"CIK{cik10(cik)}.json.gz"
    return fetch_json(url, path, headers=_headers)


def filing_index_url(cik, accn: str) -> str:
    """Human-readable link to a filing on EDGAR, from its accession number."""
    return (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accn.replace('-', '')}/{accn}-index.htm")


def facts_for_tag(cf: dict, tag: str, taxonomy: str = "us-gaap",
                  unit: str = "USD") -> pd.DataFrame:
    """All reported values of one XBRL tag, as a table (one row per fact).

    Returns an empty table if the company never used this tag.
    """
    cols = ["cik", "tag", "start", "end", "val", "accn", "form", "filed",
            "fy", "fp", "frame"]
    try:
        items = cf["facts"][taxonomy][tag]["units"][unit]
    except KeyError:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(items)
    df["cik"] = int(cf["cik"])
    df["tag"] = tag
    for c in cols:
        if c not in df.columns:
            df[c] = None
    return df[cols]


def tag_coverage(cf: dict, tags: list[str]) -> pd.DataFrame:
    """For each candidate tag: how many facts and what date range it covers.
    Used to discover which tag a company actually uses (tags differ by firm)."""
    rows = []
    for tag in tags:
        df = facts_for_tag(cf, tag)
        df = df[df["form"].isin(["10-Q", "10-K", "10-Q/A", "10-K/A"])]
        if df.empty:
            rows.append(dict(tag=tag, n_facts=0, first_end=None, last_end=None))
        else:
            rows.append(dict(tag=tag, n_facts=len(df),
                             first_end=df["end"].min(), last_end=df["end"].max()))
    return pd.DataFrame(rows)
