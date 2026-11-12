"""FRED (Federal Reserve Bank of St. Louis) series: metadata and observations.

API documentation: https://fred.stlouisfed.org/docs/api/fred/
The API key is never saved: it is stripped from the URL in SOURCES.csv.
"""

from __future__ import annotations

import pandas as pd

from .config import DATA_RAW, fred_api_key
from .sources import fetch_json

API = "https://api.stlouisfed.org/fred"


def series_info(series_id: str) -> dict:
    key = fred_api_key()
    url = f"{API}/series?series_id={series_id}&api_key={key}&file_type=json"
    path = DATA_RAW / "fred" / f"{series_id}_info.json.gz"
    data = fetch_json(url, path, redact=key)
    return data["seriess"][0]


def first_release_dates(series_id: str) -> pd.Series:
    """When each observation was FIRST published, from FRED's archive (ALFRED).
    Index = observation date, value = first publication date."""
    key = fred_api_key()
    url = (f"{API}/series/observations?series_id={series_id}&api_key={key}&file_type=json"
           "&realtime_start=1776-07-04&realtime_end=9999-12-31")
    path = DATA_RAW / "fred" / f"{series_id}_all_vintages.json.gz"
    data = fetch_json(url, path, redact=key)
    df = pd.DataFrame(data["observations"])
    df = df[df["value"] != "."]
    df["date"] = pd.to_datetime(df["date"])
    df["realtime_start"] = pd.to_datetime(df["realtime_start"])
    return df.groupby("date")["realtime_start"].min()


def observations(series_id: str) -> pd.DataFrame:
    """All observations for a series. FRED marks missing values as '.',
    which we keep as missing (NaN), never filled."""
    key = fred_api_key()
    url = f"{API}/series/observations?series_id={series_id}&api_key={key}&file_type=json"
    path = DATA_RAW / "fred" / f"{series_id}_observations.json.gz"
    data = fetch_json(url, path, redact=key)
    df = pd.DataFrame(data["observations"])[["date", "value"]]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"].replace(".", None), errors="coerce")
    df["series_id"] = series_id
    df["source_url"] = f"https://fred.stlouisfed.org/series/{series_id}"
    return df
