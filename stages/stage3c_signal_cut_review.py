"""Addendum A2, audit step (CHANGELOG v1.6): list every borrowing-base cut that
creates a signal in the primary test, for bankrupt firms AND survivors alike,
so each can be judged by hand. Then recompute the test using only cuts judged
to be real lender cuts.

This was added AFTER results were seen (an independent audit found that some
hits rest on mechanical reductions), so it is a labeled sensitivity check and
never replaces the pre-registered result. It is symmetric on purpose: cuts
behind false alarms are reviewed exactly like cuts behind hits.

Usage:
    python stages/stage3c_signal_cut_review.py list      # writes the review sheet
    python stages/stage3c_signal_cut_review.py results   # uses the filled-in sheet
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from fundgap.bbase import firm_flag
from fundgap.config import DATA_CLEAN
from fundgap.labels import WINDOW, confusion, label_firm
from stage3b_test import QUARTERS, shortfall_series

SHEET = DATA_CLEAN / "bbase_signal_cut_review.csv"


def load():
    head = pd.read_csv(DATA_CLEAN / "stage2_labels_all_variants.csv")
    head = head[(head.version == "B") & (head.bust == "B1") & (head.lender == "lender_step_back")
                & (head.vintage == "first") & (head.exits == "kept")]
    ttm = pd.read_csv(DATA_CLEAN / "stage2_ttm.csv")
    ttm["quarter"] = pd.PeriodIndex(ttm["quarter"], freq="Q")
    cuts = pd.read_csv(DATA_CLEAN / "bbase_cuts_v2.csv")
    cuts["q"] = pd.PeriodIndex(pd.to_datetime(cuts["file_date"]), freq="Q")
    return head, ttm, cuts


def scoring_window(bust_q):
    return (bust_q - 12, bust_q - 1) if bust_q is not None else WINDOW


def list_cuts():
    """Every cut whose flag (its filing quarter or the next) lands in a quarter of
    the firm's scoring window, for P (with shortfall) or S1 (cut alone)."""
    head, ttm, cuts = load()
    rows = []
    for r in head.itertuples():
        bust_q = pd.Period(r.bust_quarter) if isinstance(r.bust_quarter, str) and r.bust_quarter else None
        a, b = scoring_window(bust_q)
        sf = shortfall_series(ttm, r.cik)
        for c in cuts[cuts["cik"] == r.cik].itertuples():
            flag_qs = [q for q in (c.q, c.q + 1) if a <= q <= b]
            if not flag_qs:
                continue
            rows.append(dict(cik=r.cik, entity_name=r.entity_name, bust_quarter=r.bust_quarter or "",
                             file_date=c.file_date, form=c.form, new=c.new, old=c.old,
                             drives_P=any((q in sf.index) and pd.notna(sf[q]) and bool(sf[q]) for q in flag_qs),
                             drives_S1=True, url=c.url, sentence=c.sentence,
                             is_lender_cut="", reviewer_note=""))
    out = pd.DataFrame(rows)
    out.to_csv(SHEET, index=False)
    print(f"{len(out)} signal-creating cuts at {out.cik.nunique()} firms "
          f"({int(out.drives_P.sum())} drive a P signal)")


def results():
    head, ttm, cuts = load()
    sheet = pd.read_csv(SHEET)
    if sheet["is_lender_cut"].isna().any() or (sheet["is_lender_cut"] == "").any():
        raise SystemExit("Review sheet not fully judged.")
    out = []
    for keep, name in ((("yes",), "only cuts judged real lender cuts"),
                       (("yes", "unclear"), "real lender cuts + unclear ones")):
        bad = sheet[~sheet["is_lender_cut"].isin(keep)][["cik", "file_date", "new"]]
        bad_keys = set(zip(bad.cik, bad.file_date, bad.new))
        kept = cuts[[(k not in bad_keys) for k in zip(cuts.cik, cuts.file_date, cuts.new)]]
        lab = []
        for r in head.itertuples():
            bust_q = pd.Period(r.bust_quarter) if isinstance(r.bust_quarter, str) and r.bust_quarter else None
            lender = firm_flag(kept[kept["cik"] == r.cik], QUARTERS)
            lab.append(dict(cik=r.cik,
                            P=label_firm(shortfall_series(ttm, r.cik), lender, bust_q)["label"],
                            S1=label_firm(pd.Series(True, index=QUARTERS, dtype="boolean"), lender, bust_q)["label"]))
        lab = pd.DataFrame(lab)
        for comp in ("P", "S1"):
            out.append(dict(check=name, comparison=comp, **confusion(lab[comp])))
    res = pd.DataFrame(out)
    res.to_csv(DATA_CLEAN / "bbase_signal_cut_review_results.csv", index=False)
    print(res[["check", "comparison", "n", "TP", "FN", "FP", "TN", "bust_rate_if_signal",
               "base_rate_no_signal", "fisher_p", "probabilistic_reading"]].round(4).to_string(index=False))


if __name__ == "__main__":
    {"list": list_cuts, "results": results}[sys.argv[1] if len(sys.argv) > 1 else "list"]()
