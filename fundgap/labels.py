"""Assign each firm one label from the pre-registered test (RULE.md section 4).

    TP  busted, with a signal in at least one of the 12 quarters before the bust
    FN  busted, with no signal in those 12 quarters (a miss)
    FP  no bust 2013-2019, yet a signal in 2013Q1-2016Q4 (a false alarm)
    TN  no bust and no signal
    untestable  busted, but none of the 12 prior quarters is measurable
                (CHANGELOG v1.1 item 4)
"""

from __future__ import annotations

import pandas as pd

WINDOW = (pd.Period("2013Q1"), pd.Period("2016Q4"))


def _slice(s: pd.Series, a: pd.Period, b: pd.Period) -> pd.Series:
    return s[(s.index >= a) & (s.index <= b)]


def label_firm(shortfall: pd.Series, lender: pd.Series, bust_q: pd.Period | None) -> dict:
    """shortfall: True/False/NA per quarter (NA = not measurable).
    lender: True/False per quarter (lenders stepping back).
    bust_q: quarter of the first bust, or None."""
    shortfall = shortfall.astype("boolean")
    lender = lender.reindex(shortfall.index).astype("boolean").fillna(False)
    signal = shortfall & lender  # NA where shortfall is NA

    if bust_q is not None:
        a, b = bust_q - 12, bust_q - 1
        sf = _slice(shortfall, a, b)
        sig = _slice(signal, a, b)
        if sf.notna().sum() == 0:
            return dict(label="untestable", reason="no measurable quarter before bust",
                        first_signal=None)
        if sig.fillna(False).any():
            return dict(label="TP", reason="signal before bust",
                        first_signal=str(sig[sig.fillna(False)].index.min()))
        reason = ("shortfall but lenders not stepping back" if sf.fillna(False).any()
                  else "no shortfall: cash flow covered spending")
        return dict(label="FN", reason=reason, first_signal=None)

    sig = _slice(signal, *WINDOW).fillna(False)
    if sig.any():
        return dict(label="FP", reason="signal, no bust", first_signal=str(sig[sig].index.min()))
    return dict(label="TN", reason="no signal, no bust", first_signal=None)


def confusion(labels: pd.Series) -> dict:
    """Counts plus the rates RULE.md requires. Fisher's exact test, two-sided."""
    from scipy.stats import fisher_exact

    c = labels.value_counts()
    tp, fn, fp, tn = (int(c.get(k, 0)) for k in ("TP", "FN", "FP", "TN"))
    signaled, unsignaled = tp + fp, fn + tn
    rate_sig = tp / signaled if signaled else float("nan")
    base = fn / unsignaled if unsignaled else float("nan")
    p = fisher_exact([[tp, fp], [fn, tn]])[1] if signaled and unsignaled else float("nan")
    if not (signaled and unsignaled):
        verdict = "cannot judge (an empty row)"
    elif rate_sig <= base:
        verdict = "not supported"
    elif p < 0.05:
        verdict = "supported (pilot)"
    else:
        verdict = "mixed"
    return dict(n=tp + fn + fp + tn, TP=tp, FN=fn, FP=fp, TN=tn,
                untestable=int(c.get("untestable", 0)),
                bust_rate_if_signal=rate_sig, base_rate_no_signal=base,
                difference=rate_sig - base, fisher_p=p,
                strict_reading="falsified" if (fn + fp) > 0 else "not falsified",
                probabilistic_reading=verdict)
