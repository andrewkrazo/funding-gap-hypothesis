"""Mechanical selection of the Stage 2 universe (RULE.md section 3).

Step 1: every company EDGAR currently lists under SIC 1311.
Step 2: of those, every one whose XBRL "Assets" in the calendar-year-end-2013
        frame was at least $500 million.

No company is chosen or removed by name. The frames API returns every filer
that reported the fact for that period, including firms that later went
bankrupt or were acquired, which is what protects against survivorship bias.
"""

from __future__ import annotations

import re

import pandas as pd

from .config import DATA_RAW, sec_user_agent
from .edgar import _headers
from .sources import fetch_json, fetch_text

SIC = "1311"
MIN_ASSETS = 500_000_000
FRAME = "CY2013Q4I"


def sic_ciks(sic: str = SIC) -> list[int]:
    """All CIKs EDGAR lists under one SIC code, paging 100 at a time."""
    ciks, start = [], 0
    while True:
        url = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
               f"&SIC={sic}&type=&dateb=&owner=include&start={start}&count=100&output=atom")
        path = DATA_RAW / "edgar" / "sic_listing" / f"SIC{sic}_start{start:05d}.xml.gz"
        text = fetch_text(url, path, headers={"User-Agent": sec_user_agent()})
        page = [int(c) for c in re.findall(r"<cik>(\d+)</cik>", text)]
        if not page:
            break
        ciks.extend(page)
        start += 100
    return sorted(set(ciks))


def assets_frame(frame: str = FRAME) -> pd.DataFrame:
    url = f"https://data.sec.gov/api/xbrl/frames/us-gaap/Assets/USD/{frame}.json"
    path = DATA_RAW / "edgar" / "frames" / f"Assets_USD_{frame}.json.gz"
    data = fetch_json(url, path, headers=_headers)
    df = pd.DataFrame(data["data"])
    df["frame_url"] = url
    return df


def build_universe(sic: str = SIC) -> tuple[pd.DataFrame, dict]:
    """Return the selected firms and a dict of counts for the README funnel."""
    sic_list = sic_ciks(sic)
    frame = assets_frame()
    in_sic = frame[frame["cik"].isin(sic_list)]
    selected = in_sic[in_sic["val"] >= MIN_ASSETS].copy()
    selected = selected.rename(columns={"val": "assets_2013_usd", "end": "assets_date",
                                        "entityName": "entity_name"})
    funnel = {
        f"ciks_listed_under_sic_{sic}": len(sic_list),
        "ciks_in_assets_frame_CY2013Q4I": len(frame),
        f"sic_{sic}_and_in_frame": len(in_sic),
        "of_which_assets_ge_500m": len(selected),
    }
    cols = ["cik", "entity_name", "assets_2013_usd", "assets_date", "accn", "frame_url"]
    return selected[cols].sort_values("assets_2013_usd", ascending=False), funnel
