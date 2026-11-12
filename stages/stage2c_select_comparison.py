"""Addendum A1 (RULE.md section 6): pick the comparison boom mechanically.

Ranks every eligible non-energy 4-digit SIC sector by aggregate capex growth
from calendar 2011 to 2014 and picks the largest. Writes:

    data/clean/comparison_sector_ranking.csv   every eligible sector, ranked
    data/clean/comparison_sic_map.csv          CIK -> SIC with the source URL
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import requests

from fundgap.config import DATA_CLEAN, DATA_RAW, sec_user_agent
from fundgap.edgar import _headers, cik10
from fundgap.sources import fetch_json
from fundgap.universe import MIN_ASSETS, assets_frame

TAGS = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"]
MIN_FIRMS = 15


def excluded(sic: int) -> bool:
    """Energy-linked SIC codes listed in RULE.md section 6, step 4."""
    return (1000 <= sic <= 1499 or sic in (2911, 3533, 4922, 4923, 4924, 5171, 5172, 6792)
            or 4610 <= sic <= 4619)


def capex_frame(year: int) -> pd.Series:
    """Calendar-year capex per CIK: the first tag if present, else the second."""
    out = {}
    for tag in reversed(TAGS):  # later assignment (first tag) wins
        url = f"https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/CY{year}.json"
        path = DATA_RAW / "edgar" / "frames" / f"{tag}_USD_CY{year}.json.gz"
        try:
            data = fetch_json(url, path, headers=_headers())
        except RuntimeError:
            continue
        for r in data["data"]:
            out[r["cik"]] = r["val"]
    return pd.Series(out, name=f"capex_{year}")


def sic_map(ciks: list[int]) -> pd.DataFrame:
    """Current SIC per CIK from the submissions API. Thousands of files, so
    only the SIC fields and source URL are kept (not the raw files)."""
    path = DATA_CLEAN / "comparison_sic_map.csv"
    done = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["cik"])
    have = set(done["cik"])
    rows, H = [], {"User-Agent": sec_user_agent()}
    for i, c in enumerate(c for c in ciks if c not in have):
        url = f"https://data.sec.gov/submissions/CIK{cik10(c)}.json"
        for attempt in range(3):
            r = requests.get(url, headers=H, timeout=60)
            if r.status_code == 200:
                break
            time.sleep(2 * (attempt + 1))
        if r.status_code != 200:
            raise RuntimeError(f"SIC lookup failed ({r.status_code}) for {url}")
        j = r.json()
        rows.append(dict(cik=c, sic=j.get("sic") or None, sic_description=j.get("sicDescription"),
                         entity_name=j.get("name"), source_url=url,
                         retrieved_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
        time.sleep(0.12)  # stay under the SEC's 10 requests/second
        if len(rows) % 250 == 0:
            pd.concat([done, pd.DataFrame(rows)]).to_csv(path, index=False)
            print(f"  {len(have) + len(rows)} SIC codes fetched", flush=True)
    out = pd.concat([done, pd.DataFrame(rows)], ignore_index=True)
    out.to_csv(path, index=False)
    return out


def main():
    assets = assets_frame()
    big = assets[assets["val"] >= MIN_ASSETS][["cik", "entityName", "val"]]
    capex = pd.concat([capex_frame(2011), capex_frame(2014)], axis=1).dropna()
    cand = big.merge(capex, left_on="cik", right_index=True)
    print(f"Firms with assets >= $500M (2013): {len(big)}; with capex in both 2011 and 2014: {len(cand)}")

    sics = sic_map(sorted(cand["cik"].astype(int)))
    cand = cand.merge(sics[["cik", "sic", "sic_description"]], on="cik")
    cand = cand.dropna(subset=["sic"])
    cand["sic"] = cand["sic"].astype(int)
    cand = cand[~cand["sic"].map(excluded)]

    g = cand.groupby(["sic", "sic_description"]).agg(
        firms=("cik", "size"), capex_2011=("capex_2011", "sum"), capex_2014=("capex_2014", "sum"))
    g = g[g["firms"] >= MIN_FIRMS].reset_index()
    g["boom_ratio_2014_vs_2011"] = g["capex_2014"] / g["capex_2011"]
    g = g.sort_values("boom_ratio_2014_vs_2011", ascending=False)
    g.to_csv(DATA_CLEAN / "comparison_sector_ranking.csv", index=False)

    pd.set_option("display.width", 200)
    show = g.head(12).copy()
    show[["capex_2011", "capex_2014"]] = (show[["capex_2011", "capex_2014"]] / 1e9).round(1)
    show["boom_ratio_2014_vs_2011"] = show["boom_ratio_2014_vs_2011"].round(2)
    print(f"\nEligible sectors: {len(g)}. Top 12 by capex growth 2011->2014 ($ billions):")
    print(show.to_string(index=False))
    w = g.iloc[0]
    print(f"\nComparison boom (rule picks the top row): SIC {w['sic']} {w['sic_description']}")


if __name__ == "__main__":
    main()
