"""Addendum A2, part B: the test with a firm-level lender measure (RULE.md 7.3).

Run only after the hand validation in RULE.md 7.4 passes (precision >= 80%).

Outputs:
    data/clean/bbase_results.csv          one row per pre-registered comparison
    data/clean/bbase_labels.csv           every firm's label in every comparison
    figures/bbase_cuts_by_quarter.png     how many firms' banks cut them, by quarter
    figures/bbase_bust_rates.png          bankruptcy rate with vs without the signal
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from fundgap.bbase import SENTENCES_FILE, firm_flag
from fundgap.config import DATA_CLEAN, FIGURES
from fundgap.labels import WINDOW, confusion, label_firm

QUARTERS = pd.period_range("2012Q1", "2019Q4", freq="Q")
INK, INK2, GRID, ORANGE, GREY = "#0b0b0b", "#52514e", "#e6e5e1", "#eb6834", "#8a8984"

COMPARISONS = {
    "P": "shortfall + firm-level borrowing-base cut (primary)",
    "S1": "firm-level cut alone (no shortfall needed)",
    "S2": "P, only firms that mention a borrowing base in 2013-2016",
    "S3": "P, symmetric window (busts credited only for signals 2013Q1..min(2016Q4, quarter before bust))",
    "S4": "P, firms that stopped filing dropped",
}


def shortfall_series(ttm: pd.DataFrame, cik: int) -> pd.Series:
    t = ttm[(ttm["cik"] == cik) & (ttm["method"] == "ltm") & (ttm["vintage"] == "first")]
    t = t.set_index("quarter").reindex(QUARTERS)
    both = t["ttm_capex"].notna() & t["ttm_ocf"].notna()
    return (t["ttm_capex"] > t["ttm_ocf"]).astype("boolean").where(both, pd.NA)


def symmetric_label(sf: pd.Series, lender: pd.Series, bust_q) -> str:
    sig = (sf.astype("boolean") & lender.reindex(sf.index).astype("boolean")).fillna(False)
    if bust_q is None:
        return "FP" if sig[(sig.index >= WINDOW[0]) & (sig.index <= WINDOW[1])].any() else "TN"
    end = min(WINDOW[1], bust_q - 1)
    return "TP" if sig[(sig.index >= WINDOW[0]) & (sig.index <= end)].any() else "FN"


def run(version: str, head, ttm, has_bb) -> tuple[pd.DataFrame, pd.DataFrame]:
    cuts = pd.read_csv(DATA_CLEAN / f"bbase_cuts_{version}.csv")
    rows = []
    for r in head.itertuples():
        sf = shortfall_series(ttm, r.cik)
        lender = firm_flag(cuts[cuts["cik"] == r.cik], QUARTERS)
        bust_q = pd.Period(r.bust_quarter) if isinstance(r.bust_quarter, str) and r.bust_quarter else None
        p = label_firm(sf, lender, bust_q)
        s1 = label_firm(pd.Series(True, index=QUARTERS, dtype="boolean"), lender, bust_q)
        rows.append(dict(extraction=version, cik=r.cik, entity_name=r.entity_name,
                         bust_quarter=r.bust_quarter if isinstance(r.bust_quarter, str) else "",
                         exited=r.exited, has_borrowing_base=r.cik in has_bb,
                         n_cuts_2013_2019=int(((cuts["cik"] == r.cik) & (cuts["file_date"] >= "2013-01-01")).sum()),
                         P=p["label"], P_reason=p["reason"], P_first_signal=p["first_signal"],
                         S1=s1["label"], S3=symmetric_label(sf, lender, bust_q)))
    lab = pd.DataFrame(rows)
    lab["S2"] = lab["P"].where(lab["has_borrowing_base"])
    lab["S4"] = lab["P"].where(~lab["exited"])
    res = pd.DataFrame([dict(extraction=version, comparison=k, description=v, **confusion(lab[k].dropna()))
                        for k, v in COMPARISONS.items()])
    return lab, res


def main():
    head = pd.read_csv(DATA_CLEAN / "stage2_labels_all_variants.csv")
    head = head[(head.version == "B") & (head.bust == "B1") & (head.lender == "lender_step_back")
                & (head.vintage == "first") & (head.exits == "kept")]
    ttm = pd.read_csv(DATA_CLEAN / "stage2_ttm.csv")
    ttm["quarter"] = pd.PeriodIndex(ttm["quarter"], freq="Q")
    sents = pd.read_json(SENTENCES_FILE, lines=True, compression="gzip").dropna(subset=["sentence"])
    has_bb = set(sents[sents["form"].isin(["10-K", "10-Q", "10-K/A", "10-Q/A"])
                       & (sents["file_date"] >= "2013-01-01") & (sents["file_date"] <= "2016-12-31")]["cik"])
    labs, ress = zip(*(run(v, head, ttm, has_bb) for v in ("v1", "v2")))
    lab_all, res = pd.concat(labs, ignore_index=True), pd.concat(ress, ignore_index=True)
    lab_all.to_csv(DATA_CLEAN / "bbase_labels.csv", index=False)
    res.to_csv(DATA_CLEAN / "bbase_results.csv", index=False)
    lab = lab_all[lab_all["extraction"] == "v2"]
    cuts = pd.read_csv(DATA_CLEAN / "bbase_cuts_v2.csv")

    # ---- Figures ---------------------------------------------------------
    FIGURES.mkdir(exist_ok=True)
    c = cuts[(cuts["file_date"] >= "2013-01-01") & cuts["cik"].isin(lab["cik"])].copy()
    c["q"] = pd.PeriodIndex(pd.to_datetime(c["file_date"]), freq="Q")
    per_q = c.groupby("q")["cik"].nunique().reindex(pd.period_range("2013Q1", "2019Q4", freq="Q"), fill_value=0)
    fig, ax = plt.subplots(figsize=(8, 3))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.bar([q.end_time for q in per_q.index], per_q.values, width=60, color=ORANGE)
    ax.grid(axis="y", color=GRID)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.set_title("Firms whose banks cut their borrowing base, by quarter the cut became public (rules v2)",
                 loc="left", fontsize=10, color=INK)
    ax.set_ylabel("firms", fontsize=8, color=INK2)
    fig.tight_layout()
    fig.savefig(FIGURES / "bbase_cuts_by_quarter.png", dpi=160)
    plt.close(fig)

    main_test = pd.read_csv(DATA_CLEAN / "stage2_results_all_variants.csv")
    m = main_test[(main_test.version == "B") & (main_test.bust == "B1") & (main_test.lender == "lender_step_back")
                  & (main_test.vintage == "first") & (main_test.exits == "kept")].iloc[0]
    pick = lambda v, c: res[(res.extraction == v) & (res.comparison == c)].iloc[0]
    bars = [("Main test: national bank survey", m), ("Own bank cut + overspending (P, rules v2)", pick("v2", "P")),
            ("Own bank cut alone (S1, rules v2)", pick("v2", "S1")), ("Own bank cut + overspending (P, rules v1)", pick("v1", "P"))]
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    y, ticks, labels = 0, [], []
    for name, r in bars:
        for rate, n, color, part in ((r["bust_rate_if_signal"], r["TP"] + r["FP"], ORANGE, "with signal"),
                                     (r["base_rate_no_signal"], r["FN"] + r["TN"], GREY, "without")):
            ax.barh(y, rate * 100, color=color, height=0.7)
            ax.text(rate * 100 + 1, y, f"{rate*100:.0f}%  (n={n})", va="center", fontsize=8, color=INK)
            ticks.append(y)
            labels.append(f"{name}: {part}")
            y += 1
        y += 0.6
    ax.set_yticks(ticks)
    ax.set_yticklabels(labels, fontsize=7.5, color=INK2)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of firms that went bankrupt (8-K Item 1.03), 2013-2019", fontsize=8, color=INK2)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.set_title("Does the firm's OWN bank pulling back predict bankruptcy?", loc="left", fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(FIGURES / "bbase_bust_rates.png", dpi=160)
    plt.close(fig)

    # ---- Printed report ----------------------------------------------------
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 200)
    print("Firms:", len(lab), "| with a borrowing base 2013-16:", int(lab.has_borrowing_base.sum()),
          "| with >=1 cut 2013-2019:", int((lab.n_cuts_2013_2019 > 0).sum()))
    print("\nCuts becoming public, by quarter (firms):")
    print(per_q[per_q > 0].to_string())
    for _, r in res.iterrows():
        print(f"\n[rules {r['extraction']}, {r['comparison']}] {r['description']}")
        print(f"   signal: {r['TP']} bust / {r['FP']} no bust | no signal: {r['FN']} bust / {r['TN']} no bust"
              f" | n={r['n']}")
        print(f"   bust rate with signal {r['bust_rate_if_signal']:.1%} vs base {r['base_rate_no_signal']:.1%}"
              f" | p={r['fisher_p']:.3f} | {r['probabilistic_reading']} | strict: {r['strict_reading']}")
    print("\nPrimary (P) labels, rules v2:")
    print(lab.sort_values(["P", "entity_name"])[["entity_name", "P", "P_reason", "P_first_signal", "bust_quarter",
                                                  "n_cuts_2013_2019", "S1"]].to_string(index=False))


if __name__ == "__main__":
    main()
