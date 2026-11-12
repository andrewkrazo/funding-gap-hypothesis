"""Unit tests for the year-to-date -> quarterly logic.

Every test uses small hand-made numbers so you can check the arithmetic in
your head. None of these numbers are real company data.
"""

import math

import pandas as pd
import pytest

from fundgap.quarterly import calendar_quarter, pick_vintage, to_quarterly, trailing_four


def fact(start, end, val, filed, accn=None, form="10-Q"):
    return dict(start=start, end=end, val=val, filed=filed,
                accn=accn or f"acc-{end}-{filed}", form=form)


def calendar_year_facts():
    """A calendar-year company: YTD 10, 25, 45, then a full year of 70."""
    return pd.DataFrame([
        fact("2023-01-01", "2023-03-31", 10, "2023-05-01"),
        fact("2023-01-01", "2023-06-30", 25, "2023-08-01"),
        fact("2023-01-01", "2023-09-30", 45, "2023-11-01"),
        fact("2023-01-01", "2023-12-31", 70, "2024-02-01", form="10-K"),
    ])


def test_ytd_is_differenced_into_quarters():
    q = to_quarterly(calendar_year_facts())
    assert list(q["value"]) == [10, 15, 20, 25]
    assert [str(p) for p in q["quarter"]] == ["2023Q1", "2023Q2", "2023Q3", "2023Q4"]
    assert list(q["method"]) == ["direct", "ytd_diff", "ytd_diff", "ytd_diff"]


def test_q4_comes_from_10k_minus_nine_months():
    q = to_quarterly(calendar_year_facts())
    q4 = q[q["quarter"] == pd.Period("2023Q4")].iloc[0]
    assert q4["value"] == 70 - 45
    # Both source filings are recorded so the number can be traced.
    assert q4["accn"].count("|") == 1


def test_different_fiscal_years_are_never_subtracted():
    # Two YTD figures with DIFFERENT start dates must not be differenced.
    facts = pd.DataFrame([
        fact("2022-01-01", "2022-12-31", 100, "2023-02-01", form="10-K"),
        fact("2023-01-01", "2023-03-31", 30, "2023-05-01"),
    ])
    q = to_quarterly(facts)
    assert list(q["value"]) == [30]  # only the direct 3-month Q1


def test_non_calendar_fiscal_year_microsoft_style():
    # Fiscal year starts July 1 (like Microsoft). Ends Sep, Dec, Mar, Jun.
    facts = pd.DataFrame([
        fact("2022-07-01", "2022-09-30", 5, "2022-10-25"),
        fact("2022-07-01", "2022-12-31", 12, "2023-01-25"),
        fact("2022-07-01", "2023-03-31", 20, "2023-04-25"),
        fact("2022-07-01", "2023-06-30", 30, "2023-07-27", form="10-K"),
    ])
    q = to_quarterly(facts)
    assert list(q["value"]) == [5, 7, 8, 10]
    assert [str(p) for p in q["quarter"]] == ["2022Q3", "2022Q4", "2023Q1", "2023Q2"]


def test_oracle_style_may_year_end():
    # Fiscal year starts June 1, quarters end Aug 31, Nov 30, Feb 28, May 31.
    facts = pd.DataFrame([
        fact("2022-06-01", "2022-08-31", 3, "2022-09-15"),
        fact("2022-06-01", "2022-11-30", 7, "2022-12-15"),
        fact("2022-06-01", "2023-02-28", 12, "2023-03-15"),
        fact("2022-06-01", "2023-05-31", 20, "2023-06-20", form="10-K"),
    ])
    q = to_quarterly(facts)
    assert list(q["value"]) == [3, 4, 5, 8]
    assert [str(p) for p in q["quarter"]] == ["2022Q3", "2022Q4", "2023Q1", "2023Q2"]


def test_restatement_first_vs_latest():
    # H1 originally reported as 25, later restated to 27 in next year's 10-Q.
    facts = calendar_year_facts()
    facts = pd.concat([facts, pd.DataFrame([
        fact("2023-01-01", "2023-06-30", 27, "2024-08-01", accn="restated"),
    ])], ignore_index=True)
    first = to_quarterly(facts, mode="first")
    latest = to_quarterly(facts, mode="latest")
    assert list(first["value"]) == [10, 15, 20, 25]
    # With the restated H1 = 27: Q2 = 27 - 10 = 17 and Q3 = 45 - 27 = 18.
    assert list(latest["value"]) == [10, 17, 18, 25]


def test_pick_vintage_ignores_non_periodic_forms():
    facts = pd.DataFrame([
        fact("2023-01-01", "2023-03-31", 10, "2023-05-01"),
        fact("2023-01-01", "2023-03-31", 99, "2023-04-01", form="8-K"),
    ])
    assert list(pick_vintage(facts)["val"]) == [10]


def test_missing_quarter_is_not_filled():
    # No H1 figure: Q2 and Q3 cannot be computed and must be absent.
    facts = calendar_year_facts()
    facts = facts[facts["end"] != "2023-06-30"]
    q = to_quarterly(facts)
    assert [str(p) for p in q["quarter"]] == ["2023Q1", "2023Q4"]


def test_52_53_week_end_date_maps_to_previous_quarter():
    assert str(calendar_quarter("2023-01-03")) == "2022Q4"
    assert str(calendar_quarter("2023-04-01")) == "2023Q1"
    assert str(calendar_quarter("2022-12-31")) == "2022Q4"
    assert str(calendar_quarter("2023-03-31")) == "2023Q1"


def test_trailing_four_needs_four_consecutive_quarters():
    q = pd.DataFrame({
        "quarter": pd.period_range("2022Q1", periods=6, freq="Q"),
        "value": [1, 2, 3, 4, 5, 6],
    })
    ttm = trailing_four(q)
    assert math.isnan(ttm[pd.Period("2022Q3")])
    assert ttm[pd.Period("2022Q4")] == 10
    assert ttm[pd.Period("2023Q2")] == 3 + 4 + 5 + 6


def test_trailing_four_does_not_bridge_gaps():
    q = pd.DataFrame({
        "quarter": [pd.Period(p) for p in ["2022Q1", "2022Q2", "2022Q3", "2023Q1", "2023Q2"]],
        "value": [1, 2, 3, 5, 6],
    })
    ttm = trailing_four(q)
    # 2022Q4 is missing, so no TTM through 2023Q2 can be formed.
    assert ttm.isna().all()


def test_two_fiscal_quarters_in_one_calendar_quarter_raises():
    facts = pd.DataFrame([
        fact("2023-01-01", "2023-03-31", 10, "2023-05-01"),
        fact("2023-02-01", "2023-03-15", 99, "2023-05-01"),  # 43 days: ignored
        # 90 days ending Apr 5: within 7 days of Q2 start, so it maps to 2023Q1 too.
        fact("2023-01-06", "2023-04-05", 7, "2023-05-01"),
    ])
    with pytest.raises(ValueError):
        to_quarterly(facts)


# ---- LTM identity (ttm_from_filings) ----------------------------------------

from fundgap.quarterly import ttm_from_filings


def two_year_filings():
    """FY2022 = 60 (10-K). In 2023 each 10-Q shows this year's YTD and last
    year's YTD side by side: Q1 10 vs 8, H1 25 vs 20, 9M 45 vs 33. FY2023 = 70."""
    return pd.DataFrame([
        fact("2022-01-01", "2022-12-31", 60, "2023-02-01", accn="K22", form="10-K"),
        fact("2023-01-01", "2023-03-31", 10, "2023-05-01", accn="Q1"),
        fact("2022-01-01", "2022-03-31", 8, "2023-05-01", accn="Q1"),
        fact("2023-01-01", "2023-06-30", 25, "2023-08-01", accn="Q2"),
        fact("2022-01-01", "2022-06-30", 20, "2023-08-01", accn="Q2"),
        fact("2023-01-01", "2023-09-30", 45, "2023-11-01", accn="Q3"),
        fact("2022-01-01", "2022-09-30", 33, "2023-11-01", accn="Q3"),
        fact("2023-01-01", "2023-12-31", 70, "2024-02-01", accn="K23", form="10-K"),
        fact("2022-01-01", "2022-12-31", 60, "2024-02-01", accn="K23", form="10-K"),
    ])


def test_ltm_identity_values():
    t = ttm_from_filings(two_year_filings()).set_index("quarter")["ttm"]
    assert t[pd.Period("2022Q4")] == 60
    assert t[pd.Period("2023Q1")] == 60 + 10 - 8
    assert t[pd.Period("2023Q2")] == 60 + 25 - 20
    assert t[pd.Period("2023Q3")] == 60 + 45 - 33
    assert t[pd.Period("2023Q4")] == 70


def test_ltm_matches_quarter_sum_when_data_are_consistent():
    # With consistent tagging, both methods must agree exactly.
    f = two_year_filings()
    quarter_sum = trailing_four(to_quarterly(f)).dropna()
    ltm = ttm_from_filings(f).set_index("quarter")["ttm"]
    for q, v in quarter_sum.items():
        assert ltm[q] == v


def test_ltm_survives_a_tag_change_between_10q_and_10k():
    # The 10-K counts an extra line (tag B) that the 10-Qs fold elsewhere.
    # Quarter-by-quarter subtraction would mix the two; the LTM identity
    # uses each 10-Q's own side-by-side numbers, so it stays internally consistent.
    f = two_year_filings()
    f.loc[f["accn"] == "K23", "val"] = f.loc[f["accn"] == "K23", "val"] + 5
    t = ttm_from_filings(f).set_index("quarter")["ttm"]
    assert t[pd.Period("2023Q3")] == 60 + 45 - 33   # no contamination from K23


def test_ltm_missing_when_prior_year_not_in_same_filing():
    f = two_year_filings()
    f = f[~((f["accn"] == "Q2") & (f["end"] == "2022-06-30"))]
    t = ttm_from_filings(f)
    assert pd.Period("2023Q2") not in set(t["quarter"])


def test_ltm_non_calendar_fiscal_year():
    # Fiscal year July-June (Microsoft style).
    f = pd.DataFrame([
        fact("2021-07-01", "2022-06-30", 100, "2022-07-28", accn="K", form="10-K"),
        fact("2022-07-01", "2022-12-31", 55, "2023-01-25", accn="Q"),
        fact("2021-07-01", "2021-12-31", 50, "2023-01-25", accn="Q"),
    ])
    t = ttm_from_filings(f).set_index("quarter")["ttm"]
    assert t[pd.Period("2022Q4")] == 100 + 55 - 50
