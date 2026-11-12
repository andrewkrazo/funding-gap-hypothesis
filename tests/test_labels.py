"""Unit tests for bust labels and the confusion-table logic (made-up inputs)."""

import pandas as pd

from fundgap.busts import bankruptcy_events, capex_cut_quarter
from fundgap.labels import confusion, label_firm

Q = pd.period_range("2012Q1", "2019Q4", freq="Q")


def series(true_quarters=(), na_quarters=(), default=False):
    s = pd.Series(default, index=Q, dtype="boolean")
    for q in true_quarters:
        s[pd.Period(q)] = True
    for q in na_quarters:
        s[pd.Period(q)] = pd.NA
    return s


LENDERS = series(true_quarters=[str(q) for q in pd.period_range("2015Q3", "2016Q4", freq="Q")])


def test_true_positive_needs_signal_strictly_before_bust():
    sf = series(true_quarters=["2016Q1"])
    assert label_firm(sf, LENDERS, pd.Period("2016Q2"))["label"] == "TP"
    # Signal in the same quarter as the bust does not count.
    assert label_firm(sf, LENDERS, pd.Period("2016Q1"))["label"] == "FN"


def test_signal_more_than_12_quarters_before_bust_does_not_count():
    sf = series(true_quarters=["2015Q3"])
    assert label_firm(sf, LENDERS, pd.Period("2018Q3"))["label"] == "TP"   # 12 quarters
    assert label_firm(sf, LENDERS, pd.Period("2018Q4"))["label"] == "FN"   # 13 quarters


def test_false_negative_reasons():
    # Bust 2016Q2: its 12-quarter window 2013Q2-2016Q1 includes lender quarters 2015Q3-2016Q1.
    covered = label_firm(series(), LENDERS, pd.Period("2016Q2"))
    assert covered["label"] == "FN"
    assert covered["reason"] == "no shortfall in the 12 quarters before the bust"
    sf = series(true_quarters=["2014Q1"])  # shortfall only while lenders were easing
    assert label_firm(sf, LENDERS, pd.Period("2016Q2"))["reason"] ==         "shortfall, but never while lenders were stepping back"
    # Data stops before lenders tightened: say so instead of blaming lenders.
    gone = series(true_quarters=["2014Q1"],
                  na_quarters=[str(q) for q in pd.period_range("2015Q1", "2019Q4", freq="Q")])
    assert label_firm(gone, LENDERS, pd.Period("2016Q2"))["reason"] ==         "no data in the quarters when lenders were stepping back"
    # Bust before lenders ever tightened.
    assert label_firm(sf, LENDERS, pd.Period("2015Q1"))["reason"] ==         "lenders never stepped back in the 12 quarters before the bust"


def test_untestable_when_nothing_measurable_before_bust():
    na = [str(q) for q in pd.period_range("2012Q1", "2016Q1", freq="Q")]
    sf = series(na_quarters=na)
    assert label_firm(sf, LENDERS, pd.Period("2016Q2"))["label"] == "untestable"


def test_false_positive_and_true_negative():
    assert label_firm(series(true_quarters=["2016Q1"]), LENDERS, None)["label"] == "FP"
    # A signal after 2016Q4 is outside the window: no bust and no in-window signal = TN.
    late_lenders = series(true_quarters=["2018Q4"])
    assert label_firm(series(true_quarters=["2018Q4"]), late_lenders, None)["label"] == "TN"


def test_capex_cut_rule():
    s = pd.Series([100, 100, 100, 100, 80, 60, 50, 40], index=pd.period_range("2014Q1", periods=8, freq="Q"))
    assert capex_cut_quarter(s) == pd.Period("2015Q3")  # 50 <= 0.5 * 100
    # Needs at least 4 earlier values.
    short = pd.Series([100, 40], index=pd.period_range("2014Q1", periods=2, freq="Q"))
    assert capex_cut_quarter(short) is None


def test_bankruptcy_item_parsing():
    f = pd.DataFrame(dict(
        cik=[1, 1, 1, 1],
        accessionNumber=["a", "b", "c", "d"],
        filingDate=["2016-05-02", "2016-05-02", "2016-06-01", "2016-07-01"],
        reportDate=["2016-04-30", "", "", ""],
        form=["8-K", "8-K", "10-Q", "8-K"],
        items=["1.03,2.04,7.01", "2.03", "", "1.031"],   # "1.031" must NOT match
    ))
    ev = bankruptcy_events(f)
    assert list(ev["accessionNumber"]) == ["a"]
    assert list(ev["event_date"]) == ["2016-04-30"]


def test_confusion_counts_and_verdicts():
    labels = pd.Series(["TP"] * 8 + ["FP"] * 2 + ["FN"] * 2 + ["TN"] * 8 + ["untestable"])
    c = confusion(labels)
    assert (c["TP"], c["FP"], c["FN"], c["TN"], c["untestable"]) == (8, 2, 2, 8, 1)
    assert c["bust_rate_if_signal"] == 0.8 and c["base_rate_no_signal"] == 0.2
    assert c["probabilistic_reading"] == "supported (pilot)"
    assert c["strict_reading"] == "falsified"
    flat = confusion(pd.Series(["TP", "FP", "FN", "TN"]))
    assert flat["probabilistic_reading"] == "not supported"


def test_bankruptcy_events_with_no_8ks_at_all():
    # Foreign filers file 6-Ks, not 8-Ks: the result must be an empty table, not an error.
    f = pd.DataFrame(dict(cik=[1], accessionNumber=["a"], filingDate=["2016-05-02"],
                          reportDate=[""], form=["6-K"], items=[""]))
    ev = bankruptcy_events(f)
    assert ev.empty and "event_date" in ev.columns


def test_verified_mistagged_8k_is_not_a_bankruptcy():
    # EDGAR metadata says 1.03, but the document is an officer resignation.
    f = pd.DataFrame(dict(cik=[1518909], accessionNumber=["0001518909-14-000034"],
                          filingDate=["2014-09-19"], reportDate=["2014-09-15"], form=["8-K"],
                          items=["1.03,5.02,9.01"]))
    assert bankruptcy_events(f).empty
