"""Turn SEC XBRL cash-flow facts into true quarterly values.

THE TRAP THIS FILE HANDLES
--------------------------
Cash-flow statements in 10-Q filings are *year-to-date* (YTD). A company's
second-quarter 10-Q reports cash flow for the first SIX months, not for the
second quarter alone. So to get each quarter on its own we subtract:

    Q1 = YTD through Q1            (3 months)
    Q2 = YTD through Q2 - YTD Q1   (6 months - 3 months)
    Q3 = YTD through Q3 - YTD Q2   (9 months - 6 months)
    Q4 = full year (10-K) - YTD Q3 (12 months - 9 months)

We only subtract two YTD numbers if they share the SAME start date, which is
the first day of the fiscal year. That one check keeps us from mixing up two
different fiscal years.

Each XBRL fact we receive looks like this (one dict per reported number):
    {"start": "2023-01-01", "end": "2023-06-30", "val": 123, "accn": "...",
     "form": "10-Q", "filed": "2023-07-28"}

The same period is often reported several times: in the original filing,
again as a comparison column a year later, and again if restated. RULE.md
section 2.1 says the primary analysis uses the value AS FIRST REPORTED (the
earliest filing). The "latest" mode is a sensitivity check.

Nothing in this file fills in, estimates or interpolates a missing value.
"""

from __future__ import annotations

import pandas as pd

# A "quarter" is any period lasting 80-100 days (calendar quarters run 90-92
# days; 52/53-week fiscal calendars give 84 or 91 days).
QUARTER_MIN_DAYS = 80
QUARTER_MAX_DAYS = 100
# Anything longer than a quarter and at most about a year is a YTD figure.
YEAR_MAX_DAYS = 380

# Only these forms carry the company's own periodic financial statements.
PERIODIC_FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A", "10-KT", "10-KT/A"}


def calendar_quarter(end_date) -> pd.Period:
    """Map a fiscal period's end date to a calendar quarter (RULE.md 2.1).

    Normally that is the calendar quarter containing the end date. Exception:
    companies on 52/53-week years sometimes end a quarter a few days into the
    next calendar quarter (e.g. Jan 3). An end date in the first 7 days of a
    calendar quarter is assigned to the PREVIOUS quarter.
    """
    end = pd.Timestamp(end_date)
    q = end.to_period("Q")
    first_day_of_q = q.start_time
    if (end - first_day_of_q).days < 7:
        q = q - 1
    return q


def pick_vintage(facts: pd.DataFrame, mode: str = "first") -> pd.DataFrame:
    """Keep one value per (start, end) period.

    mode="first":  the earliest-filed value (what people saw at the time).
    mode="latest": the most recently filed value (after any restatement).
    Ties on the filing date are broken by accession number so the result is
    always the same on every run.
    """
    if mode not in ("first", "latest"):
        raise ValueError("mode must be 'first' or 'latest'")
    df = facts[facts["form"].isin(PERIODIC_FORMS)].copy()
    df = df.dropna(subset=["start", "end", "val"])
    ascending = mode == "first"
    df = df.sort_values(["start", "end", "filed", "accn"],
                        ascending=[True, True, ascending, ascending])
    return df.drop_duplicates(subset=["start", "end"], keep="first")


def to_quarterly(facts: pd.DataFrame, mode: str = "first") -> pd.DataFrame:
    """Return one row per fiscal quarter with a true (non-YTD) value.

    Output columns:
        quarter      calendar quarter (pandas Period, e.g. 2023Q2)
        start, end   the fiscal quarter's own dates
        value        the quarterly value
        method       "direct" (a 3-month fact) or "ytd_diff" (subtracted)
        accn         accession number(s) used, joined with "|"
        filed        filing date(s) used, joined with "|"
    """
    df = pick_vintage(facts, mode).copy()
    df["start"] = pd.to_datetime(df["start"])
    df["end"] = pd.to_datetime(df["end"])
    df["days"] = (df["end"] - df["start"]).dt.days + 1

    rows = {}  # keyed by quarter end date, so a direct value wins over a derived one

    # 1) Facts that already cover exactly one quarter are used directly.
    direct = df[(df["days"] >= QUARTER_MIN_DAYS) & (df["days"] <= QUARTER_MAX_DAYS)]
    for r in direct.itertuples():
        rows[r.end] = dict(start=r.start, end=r.end, value=r.val, method="direct",
                           accn=r.accn, filed=r.filed)

    # 2) Year-to-date facts: within each fiscal year (same start date), the
    #    difference between consecutive YTD figures is one quarter.
    ytd = df[(df["days"] >= QUARTER_MIN_DAYS) & (df["days"] <= YEAR_MAX_DAYS)]
    for start, group in ytd.groupby("start"):
        group = group.sort_values("end")
        prev = None
        for r in group.itertuples():
            if prev is not None:
                gap = (r.end - prev.end).days
                is_one_quarter_later = QUARTER_MIN_DAYS <= gap <= QUARTER_MAX_DAYS
                if is_one_quarter_later and r.end not in rows:
                    rows[r.end] = dict(
                        start=prev.end + pd.Timedelta(days=1), end=r.end,
                        value=r.val - prev.val, method="ytd_diff",
                        accn=f"{prev.accn}|{r.accn}", filed=f"{prev.filed}|{r.filed}")
            prev = r

    if not rows:
        return pd.DataFrame(columns=["quarter", "start", "end", "value",
                                     "method", "accn", "filed"])
    out = pd.DataFrame(rows.values()).sort_values("end").reset_index(drop=True)
    out.insert(0, "quarter", out["end"].map(calendar_quarter))

    # Two different fiscal quarters must never land in the same calendar
    # quarter. If they do, something is wrong with the data: stop loudly
    # rather than silently keep one.
    dupes = out[out["quarter"].duplicated(keep=False)]
    if not dupes.empty:
        raise ValueError(f"Two fiscal quarters map to one calendar quarter:\n{dupes}")
    return out


def trailing_four(quarterly: pd.DataFrame, value_col: str = "value") -> pd.Series:
    """Trailing-four-quarter (TTM) sum, indexed by calendar quarter.

    The result is missing unless all four quarters exist AND are consecutive.
    A gap in the data is never bridged.
    """
    s = quarterly.set_index("quarter")[value_col].sort_index()
    if s.empty:
        return s.astype(float)
    full_index = pd.period_range(s.index.min(), s.index.max(), freq="Q")
    s = s.reindex(full_index)  # missing quarters become NaN here
    return s.rolling(4, min_periods=4).sum()
