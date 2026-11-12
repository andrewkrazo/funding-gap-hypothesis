"""Lender-conditions proxies, aligned to calendar quarters (RULE.md 2.5)."""

from __future__ import annotations

import pandas as pd

from . import fred


def lender_table() -> pd.DataFrame:
    """One row per calendar quarter.

    DRTSCILM: the survey dated the first day of quarter Q+1 asks banks about
    the previous three months, so its value describes quarter Q.
    BAA10Y (side check): quarterly average of the daily spread, flagged when
    above the median of the previous 20 quarterly averages.
    """
    sloos = fred.observations("DRTSCILM").dropna(subset=["value"])
    sloos["quarter"] = sloos["date"].dt.to_period("Q") - 1  # describes the prior quarter
    sloos = sloos.rename(columns={"value": "drtscilm", "date": "drtscilm_survey_date"})
    sloos["lender_step_back"] = sloos["drtscilm"] > 0

    baa = fred.observations("BAA10Y").dropna(subset=["value"])
    baa["quarter"] = baa["date"].dt.to_period("Q")
    baa_q = baa.groupby("quarter")["value"].agg(["mean", "count"]).rename(
        columns={"mean": "baa10y_qavg", "count": "baa10y_days"})
    # Trailing median of the PREVIOUS 20 quarters (shift(1) keeps the current
    # quarter out of its own benchmark).
    baa_q["baa10y_trailing20_median"] = (
        baa_q["baa10y_qavg"].shift(1).rolling(20, min_periods=20).median())
    flag = (baa_q["baa10y_qavg"] > baa_q["baa10y_trailing20_median"]).astype("boolean")
    # No benchmark yet (first 20 quarters) means "unknown", not "no".
    baa_q["baa10y_flag"] = flag.mask(baa_q["baa10y_trailing20_median"].isna())

    out = sloos.set_index("quarter")[["drtscilm", "drtscilm_survey_date",
                                      "lender_step_back"]].join(baa_q, how="outer")
    out["drtscilm_source"] = "https://fred.stlouisfed.org/series/DRTSCILM"
    out["baa10y_source"] = "https://fred.stlouisfed.org/series/BAA10Y"
    return out
