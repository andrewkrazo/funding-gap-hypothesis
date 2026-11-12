"""Unit tests for the borrowing-base cut rules. All sentences are made up,
written to look like typical filing language, before any real filing was read."""

import pandas as pd

from fundgap.bbase import dedupe_cuts, find_cut, firm_flag, to_dollars


def test_money_parsing():
    assert to_dollars("1.25", "billion") == 1.25e9
    assert to_dollars("350", "million") == 350e6
    assert to_dollars("1,250,000", None) == 1_250_000


def test_reduced_from_to():
    c = find_cut("In April 2016, the borrowing base under our Credit Facility was reduced from "
                 "$1.2 billion to $800 million.")
    assert c == dict(new=800e6, old=1.2e9, rule="from_to")


def test_reduced_to_without_from():
    c = find_cut("As a result of the spring redetermination, the borrowing base was reduced to $350.0 million.")
    assert c["new"] == 350e6 and c["old"] is None


def test_lenders_reduced():
    c = find_cut("On May 2, 2016, the lenders under the Credit Agreement reduced the borrowing base to $275 million.")
    assert c["new"] == 275e6


def test_redetermined_from_to_is_a_cut_only_if_lower():
    assert find_cut("The borrowing base was redetermined from $500 million to $350 million.")["new"] == 350e6
    assert find_cut("The borrowing base was redetermined from $350 million to $500 million.") is None


def test_increase_is_not_a_cut():
    assert find_cut("In October 2014 the borrowing base was increased from $400 million to $600 million.") is None


def test_reaffirmed_is_not_a_cut():
    assert find_cut("The lenders reaffirmed the borrowing base at $1.0 billion.") is None


def test_hypothetical_risk_language_is_not_a_cut():
    assert find_cut("If commodity prices decline, our borrowing base could be reduced to $200 million, "
                    "which may require repayment.") is None
    assert find_cut("Our borrowing base may be reduced in future redeterminations.") is None


def test_voluntary_reduction_is_not_a_cut():
    assert find_cut("We elected to reduce the borrowing base from $900 million to $600 million "
                    "to lower commitment fees.") is None


def test_dedupe_same_cut_reported_twice():
    cuts = pd.DataFrame(dict(file_date=["2016-05-05", "2016-08-04", "2017-05-04"],
                             new=[350e6, 350e6, 250e6]))
    d = dedupe_cuts(cuts)
    assert list(d["file_date"]) == ["2016-05-05", "2017-05-04"]


def test_flag_covers_report_quarter_and_next():
    qs = pd.period_range("2016Q1", "2016Q4", freq="Q")
    f = firm_flag(pd.DataFrame(dict(file_date=["2016-05-05"])), qs)
    assert list(f) == [False, True, True, False]


def test_month_may_is_not_hypothetical():
    c = find_cut("In May 2016, the borrowing base was reduced from $600 million to $450 million.")
    assert c["new"] == 450e6


# ---- Version 2 (CHANGELOG v1.5): mechanical reductions are not lender pullbacks ----

def test_v2_excludes_reduction_triggered_by_bond_issue():
    s = "Upon the issuance of the senior notes, the borrowing base was automatically reduced to $600 million."
    assert find_cut(s) is not None          # version 1 counted these
    assert find_cut(s, strict=True) is None  # version 2 does not


def test_v2_excludes_reduction_after_asset_sale():
    s = "Following the sale of our Permian properties, the borrowing base was reduced from $400 million to $300 million."
    assert find_cut(s, strict=True) is None


def test_v2_keeps_redetermination_cut():
    s = "As part of the spring redetermination, the borrowing base was reduced from $475.0 million to $200.0 million."
    assert find_cut(s, strict=True)["new"] == 200e6


def test_v2_drops_impossible_amounts():
    s = "The borrowing base was decreased by the lenders to $2 85 million."
    assert find_cut(s, strict=True) is None


def test_v2_dedupes_retold_cuts_at_any_distance():
    cuts = pd.DataFrame(dict(file_date=["2017-11-08", "2019-03-06"], new=[450e6, 450e6]))
    assert len(dedupe_cuts(cuts)) == 2                    # version 1: 270-day limit
    assert len(dedupe_cuts(cuts, window_days=None)) == 1  # version 2: same cut
