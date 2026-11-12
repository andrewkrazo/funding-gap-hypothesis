"""Stage 2, part A: universe, tag mapping, TTM tables, data checks.

Runs BEFORE any bust information is downloaded (RULE.md 2.3 step 4, the
blindness safeguard). Its outputs are committed before part B exists.

Outputs:
    data/clean/stage2_universe.csv         the mechanically selected firms
    data/stage2_tag_map.csv                capex/OCF tags actually used per firm
    data/clean/stage2_ttm.csv              TTM capex & OCF: both methods, both vintages
    data/clean/stage2_checks.csv           per-firm data checks and inclusion status
    data/clean/stage2_investing_flags.csv  years where capex > estimated investing outflows
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from fundgap import build, edgar
from fundgap.config import DATA_CLEAN, ROOT
from fundgap.quarterly import PERIODIC_FORMS, to_quarterly, trailing_four, ttm_from_filings
from fundgap.tags import CAPEX_TAGS, INVESTING_TAG, OCF_TAGS
from fundgap.universe import build_universe

WINDOW = ("2013Q1", "2016Q4")       # signal window (RULE.md section 4)
DATA_RANGE = ("2012Q1", "2019Q4")    # quarters kept
TOTAL_TAG = "PaymentsToAcquireProductiveAssets"

# Usage: python stage2a_universe_and_tags.py [SIC] [PREFIX]
# Defaults (1311, "stage2") reproduce the main oil and gas test.
SIC_CODE = sys.argv[1] if len(sys.argv) > 1 else "1311"
PREFIX = sys.argv[2] if len(sys.argv) > 2 else "stage2"

# Investing inflows used only for the capex sanity check. "Proceeds..." tags
# containing these words are financing, not investing, so they are skipped.
FINANCING_WORDS = ("Issuance", "Debt", "Borrow", "LineOfCredit", "LinesOfCredit",
                   "NotesPayable", "Stock", "Warrant", "Contribution", "Partner",
                   "Units", "Loan", "Repurchase", "Bank", "Credit", "Lease", "Notes",
                   "Bonds", "Commercial", "Subordinated", "Convertible", "Preferred")


def capex_facts(ciks: list[int], fix_double_count: bool = True) -> pd.DataFrame:
    """Build capex facts per RULE.md 2.3: within one filing and period, use the
    total tag alone if reported; otherwise sum the distinct candidate tags."""
    parts = [build.tag_facts(ciks, t) for t in CAPEX_TAGS]
    df = pd.concat([p for p in parts if not p.empty] or [parts[0]], ignore_index=True)
    df = df[df["form"].isin(PERIODIC_FORMS)].drop_duplicates(["accn", "start", "end", "tag"])
    rows = []
    for (accn, start, end), g in df.groupby(["accn", "start", "end"]):
        if TOTAL_TAG in set(g["tag"]):
            g = g[g["tag"] == TOTAL_TAG]
        elif fix_double_count and len(g) >= 3:
            # A tag equal (within 1%) to the sum of the others is a total of
            # those lines; use it alone instead of adding it to its own parts.
            # (Double-count fix, logged in CHANGELOG; same logic as RULE.md 2.3 step 1.)
            total = g["val"].sum()
            is_total = [(total - v) > 0 and abs(v - (total - v)) <= 0.01 * (total - v)
                        for v in g["val"]]
            if any(is_total):
                g = g[is_total].iloc[[0]]
        short = sorted(t.replace("PaymentsTo", "") for t in g["tag"])
        rows.append(dict(cik=g["cik"].iloc[0], start=start, end=end, val=g["val"].sum(),
                         accn=accn, form=g["form"].iloc[0], filed=g["filed"].iloc[0],
                         tagset="+".join(short)))
    return pd.DataFrame(rows)


def investing_check(ciks: list[int], capex: pd.DataFrame) -> pd.DataFrame:
    """Annual check: capex should not exceed estimated total investing outflows
    (= -net investing cash flow + investing inflows). Returns flagged years.
    Known weakness: inflows tagged with company-specific tags are missed, so
    years with big asset sales can be flagged even when nothing is wrong."""
    inv = build.tag_facts(ciks, INVESTING_TAG)
    if inv.empty or capex.empty:
        return pd.DataFrame()
    cf_all = [edgar.companyfacts(c)["facts"].get("us-gaap", {}) for c in ciks]
    inflow_tags = sorted({t for g in cf_all for t in g if t.startswith("Proceeds")
                          and not any(w in t for w in FINANCING_WORDS)})
    infl = pd.concat([build.tag_facts(ciks, t) for t in inflow_tags] or [pd.DataFrame()],
                     ignore_index=True)
    out = []
    annual = capex[(pd.to_datetime(capex["end"]) - pd.to_datetime(capex["start"])).dt.days > 350]
    for r in annual.itertuples():
        net = inv[(inv["accn"] == r.accn) & (inv["start"] == r.start) & (inv["end"] == r.end)]
        if net.empty:
            continue
        inflow = 0.0
        if not infl.empty:
            m = infl[(infl["accn"] == r.accn) & (infl["start"] == r.start) & (infl["end"] == r.end)]
            inflow = m.drop_duplicates("tag")["val"].sum()
        outflows = -net["val"].iloc[0] + inflow
        if r.val > outflows * 1.02:
            out.append(dict(cik=r.cik, fy_end=r.end, capex=r.val, est_investing_outflows=outflows,
                            accn=r.accn, tagset=r.tagset))
    return pd.DataFrame(out)


def double_count_flags(parts: pd.DataFrame) -> int:
    """Count filing-periods where one summed capex tag equals (within 1%) the
    sum of the others: the signature of a subtotal added to its own parts."""
    n = 0
    parts = parts[parts["form"].isin(PERIODIC_FORMS)].drop_duplicates(["accn", "start", "end", "tag"])
    for _, g in parts.groupby(["accn", "start", "end"]):
        if len(g) < 3 or TOTAL_TAG in set(g["tag"]):
            continue
        total = g["val"].sum()
        for v in g["val"]:
            rest = total - v
            if rest > 0 and abs(v - rest) <= 0.01 * rest:
                n += 1
                break
    return n


def ttm_tables(ciks: list[int], cfacts: pd.DataFrame, cfacts_raw: pd.DataFrame) -> pd.DataFrame:
    """TTM capex and OCF for the two analysis versions, both vintages.
    method 'ltm'         = Version B (corrected): LTM identity + double-count fix
    method 'quarter_sum' = Version A (as pre-registered): four differenced
                           quarters, capex rule exactly as written"""
    ocf_facts = build.priority_facts(ciks, OCF_TAGS)
    rows = []
    for vintage in ("first", "latest"):
        for series, facts, raw in (("ocf", ocf_facts, ocf_facts), ("capex", cfacts, cfacts_raw)):
            if facts is None or facts.empty:
                continue
            for r in ttm_from_filings(facts, vintage).itertuples():
                rows.append(dict(quarter=r.quarter, series=series, method="ltm",
                                 vintage=vintage, ttm=r.ttm, accn=r.accn))
            try:
                for q, v in trailing_four(to_quarterly(raw, vintage)).dropna().items():
                    rows.append(dict(quarter=q, series=series, method="quarter_sum",
                                     vintage=vintage, ttm=v, accn=""))
            except ValueError:
                pass  # conflicting fiscal quarters: pre-registered method unavailable
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    t = t[(t["quarter"] >= pd.Period(DATA_RANGE[0])) & (t["quarter"] <= pd.Period(DATA_RANGE[1]))]
    key = ["quarter", "method", "vintage"]
    wide = t.pivot_table(index=key, columns="series", values="ttm", aggfunc="first")
    accn = t[t["method"] == "ltm"].pivot_table(index=key, columns="series", values="accn",
                                                aggfunc="first").add_suffix("_accn")
    wide = wide.join(accn, how="left").reset_index()
    return wide.rename(columns={"capex": "ttm_capex", "ocf": "ttm_ocf"})


def main():
    DATA_CLEAN.mkdir(parents=True, exist_ok=True)
    universe, funnel = build_universe(SIC_CODE)
    universe.to_csv(DATA_CLEAN / f"{PREFIX}_universe.csv", index=False)
    print("Funnel:", funnel)

    ttm_rows, checks, tagmap, inv_flags = [], [], [], []
    w0, w1 = pd.Period(WINDOW[0]), pd.Period(WINDOW[1])
    for f in universe.itertuples():
        ciks = [int(f.cik)]
        cfacts = capex_facts(ciks)
        cfacts_raw = capex_facts(ciks, fix_double_count=False)
        parts = pd.concat([build.tag_facts(ciks, t) for t in CAPEX_TAGS], ignore_index=True)
        ocf_used = build.priority_facts(ciks, OCF_TAGS)
        t = ttm_tables(ciks, cfacts, cfacts_raw)
        status, note, n_meas, n_meas_qs, agree = "included", "", 0, 0, None
        if t.empty or "ttm_capex" not in t or "ttm_ocf" not in t:
            status = "excluded: insufficient data"
            note = "no OCF tags" if ocf_used.empty else "no capex tags"
        else:
            t.insert(0, "cik", f.cik)
            ttm_rows.append(t)

            def measurable(method):
                m = t[(t["method"] == method) & (t["vintage"] == "first")].dropna(
                    subset=["ttm_capex", "ttm_ocf"])
                return m[(m["quarter"] >= w0) & (m["quarter"] <= w1)]

            p, s = measurable("ltm"), measurable("quarter_sum")
            n_meas, n_meas_qs = len(p), len(s)
            both = p.merge(s, on="quarter", suffixes=("_p", "_s"))
            if not both.empty:
                agree = float(((both["ttm_capex_p"] > both["ttm_ocf_p"]) ==
                               (both["ttm_capex_s"] > both["ttm_ocf_s"])).mean())
            if n_meas < 4:
                status = "excluded: insufficient data"
                note = f"{n_meas} measurable TTM quarters in {WINDOW[0]}-{WINDOW[1]} (need 4)"
        fl = investing_check(ciks, cfacts)
        if not fl.empty:
            fl = fl[(fl["fy_end"] >= "2012-01-01") & (fl["fy_end"] <= "2019-12-31")]
            inv_flags.append(fl)
        tagmap.append(dict(
            cik=f.cik, entity_name=f.entity_name,
            ocf_tags=" | ".join(sorted(set(ocf_used["tag"]))) if not ocf_used.empty else "",
            capex_tagsets_seen=" ; ".join(sorted(set(cfacts["tagset"]))) if not cfacts.empty else ""))
        checks.append(dict(
            cik=f.cik, entity_name=f.entity_name, status=status, note=note,
            measurable_quarters_primary=n_meas,
            measurable_quarters_preregistered=n_meas_qs,
            shortfall_flag_agreement_between_methods=agree,
            double_count_flags=double_count_flags(parts) if not parts.empty else 0,
            investing_flag_years=0 if fl.empty else fl["fy_end"].nunique()))

    pd.concat(ttm_rows, ignore_index=True).to_csv(DATA_CLEAN / f"{PREFIX}_ttm.csv", index=False)
    pd.DataFrame(tagmap).to_csv(ROOT / "data" / f"{PREFIX}_tag_map.csv", index=False)
    inv = pd.concat(inv_flags, ignore_index=True) if inv_flags else pd.DataFrame()
    inv.to_csv(DATA_CLEAN / f"{PREFIX}_investing_flags.csv", index=False)
    checks = pd.DataFrame(checks)
    checks.to_csv(DATA_CLEAN / f"{PREFIX}_checks.csv", index=False)

    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 200)
    print("\nInclusion status:")
    print(checks["status"].value_counts().to_string())
    print("\nExcluded firms:")
    print(checks[checks["status"] != "included"][["cik", "entity_name", "status", "note"]].to_string(index=False))
    inc = checks[checks["status"] == "included"]
    print(f"\nMeasurable firm-quarters in window: primary {inc.measurable_quarters_primary.sum()}, "
          f"pre-registered {inc.measurable_quarters_preregistered.sum()}")
    print("Shortfall yes/no agreement between methods, median firm:",
          round(inc["shortfall_flag_agreement_between_methods"].median(), 3),
          "| firms below 90% agreement:",
          int((inc["shortfall_flag_agreement_between_methods"] < 0.9).sum()))
    print("Firms with possible subtotal double-counting:", int((inc["double_count_flags"] > 0).sum()),
          "| firm-years flagged by investing check:", int(inc["investing_flag_years"].sum()))
    low = inc[(inc["shortfall_flag_agreement_between_methods"] < 0.9) | (inc["double_count_flags"] > 0)]
    print(low[["cik", "entity_name", "measurable_quarters_primary",
               "shortfall_flag_agreement_between_methods", "double_count_flags"]].to_string(index=False))


if __name__ == "__main__":
    main()
