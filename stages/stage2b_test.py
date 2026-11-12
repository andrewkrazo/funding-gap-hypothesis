"""Stage 2, part B: bust labels and the pre-registered test (RULE.md section 4).

Runs only after part A's tag map and TTM tables were committed (blindness
safeguard). Reports every variant RULE.md and CHANGELOG v1.1 require:

    version   A (as pre-registered) | B (corrected, CHANGELOG v1.1)
    bust      B1 bankruptcy (primary) | B2 bankruptcy or 50% capex cut
    lender    DRTSCILM > 0 (primary) | BAA10Y side check
    vintage   first reported (primary) | latest filed
    exits     kept as no-bust (primary) | dropped

Headline = version B, B1, DRTSCILM, first reported, exits kept. Version A with
the same settings is shown right next to it.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fundgap.busts import (all_filings, bankruptcy_events, capex_cut_quarter,
                           last_periodic_filing, to_quarter)
from fundgap.config import DATA_CLEAN, FIGURES
from fundgap.labels import WINDOW, confusion, label_firm
from fundgap.lenders import lender_table

QUARTERS = pd.period_range("2012Q1", "2019Q4", freq="Q")
EXIT_CUTOFF = "2019-10-01"
EP_ENERGY_LLC = 1555082          # duplicate subsidiary dropped in version B
VERSIONS = {"A": "quarter_sum", "B": "ltm"}

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
C_NODATA, C_NONE, C_SHORT, C_SIGNAL, C_BUST = "#f4f3f0", "#dcdbd6", "#f6c3a9", "#eb6834", "#0b0b0b"


def firm_status(universe: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Bankruptcy events (all of them, with sources) and one status row per firm."""
    events, rows = [], []
    for f in universe.itertuples():
        filings = all_filings(f.cik)
        ev = bankruptcy_events(filings)
        events.append(ev.assign(entity_name=f.entity_name))
        last = last_periodic_filing(filings)
        first_b1 = ev.iloc[0] if not ev.empty else None
        rows.append(dict(
            cik=f.cik, entity_name=f.entity_name,
            b1_date=None if first_b1 is None else first_b1["event_date"],
            b1_quarter=None if first_b1 is None else str(to_quarter(first_b1["event_date"])),
            b1_accession=None if first_b1 is None else first_b1["accessionNumber"],
            b1_source=None if first_b1 is None else first_b1["source_url"],
            last_periodic_filing=last,
            exited=(first_b1 is None) and (last is None or last < EXIT_CUTOFF)))
    cols = ["cik", "entity_name", "form", "filingDate", "reportDate", "event_date", "items",
            "accessionNumber", "source_url"]
    ev_all = pd.concat(events, ignore_index=True)
    return (ev_all[cols] if not ev_all.empty else pd.DataFrame(columns=cols)), pd.DataFrame(rows)


def firm_series(ttm: pd.DataFrame, cik: int, method: str, vintage: str):
    t = ttm[(ttm["cik"] == cik) & (ttm["method"] == method) & (ttm["vintage"] == vintage)]
    t = t.set_index("quarter").reindex(QUARTERS)
    both = t["ttm_capex"].notna() & t["ttm_ocf"].notna()
    shortfall = (t["ttm_capex"] > t["ttm_ocf"]).astype("boolean").where(both, pd.NA)
    return shortfall, t["ttm_capex"]


def measurable_in_window(shortfall: pd.Series) -> int:
    w = shortfall[(shortfall.index >= WINDOW[0]) & (shortfall.index <= WINDOW[1])]
    return int(w.notna().sum())


def run_variant(universe, status, ttm, lenders, version, bust_def, lender_col, vintage, exits):
    method = VERSIONS[version]
    lender = lenders[lender_col].reindex(QUARTERS).astype("boolean").fillna(False)
    out = []
    for f in universe.itertuples():
        if version == "B" and f.cik == EP_ENERGY_LLC:
            continue
        st = status.loc[f.cik]
        if exits == "dropped" and st["exited"]:
            continue
        shortfall, capex = firm_series(ttm, f.cik, method, vintage)
        # Inclusion: >= 4 measurable quarters in the window, judged on the
        # first-reported vintage so both vintages use the same firms.
        sf_first, _ = firm_series(ttm, f.cik, method, "first")
        if measurable_in_window(sf_first) < 4:
            continue
        b1 = st["b1_quarter"]
        bust_q = pd.Period(b1) if isinstance(b1, str) and b1 else None   # NaN = no bankruptcy
        cut_q = None
        if bust_def == "B2":
            cut_q = capex_cut_quarter(capex)
            if cut_q is not None and (bust_q is None or cut_q < bust_q):
                bust_q = cut_q
        lab = label_firm(shortfall, lender, bust_q)
        out.append(dict(cik=f.cik, entity_name=f.entity_name, bust_quarter=str(bust_q) if bust_q else "",
                        bust_type=("" if bust_q is None else
                                   "bankruptcy" if cut_q is None or str(bust_q) == st["b1_quarter"]
                                   else "capex cut"),
                        exited=bool(st["exited"]), **lab))
    return pd.DataFrame(out)


def timeline_figure(labels: pd.DataFrame, ttm: pd.DataFrame, lenders: pd.DataFrame, path: Path):
    order = {"TP": 0, "FN": 1, "untestable": 2, "FP": 3, "TN": 4}
    titles = {"TP": "Busted, signal came first (TP)", "FN": "Busted, no signal (FN, miss)",
              "untestable": "Busted, no data before bust (untestable)",
              "FP": "Signal, no bust (FP, false alarm)", "TN": "No signal, no bust (TN)"}
    lab = labels.assign(o=labels["label"].map(order)).sort_values(["o", "entity_name"])
    qs = pd.period_range("2012Q4", "2019Q4", freq="Q")
    lender = lenders["lender_step_back"].reindex(qs).astype("boolean").fillna(False)
    grid = np.zeros((len(lab), len(qs), 3))
    hexrgb = lambda h: [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    for i, r in enumerate(lab.itertuples()):
        sf, _ = firm_series(ttm, r.cik, "ltm", "first")
        sf = sf.reindex(qs)
        for j, q in enumerate(qs):
            v = sf[q]
            c = C_NODATA if pd.isna(v) else (C_SIGNAL if (v and lender[q]) else C_SHORT if v else C_NONE)
            if r.bust_quarter and str(q) == r.bust_quarter:
                c = C_BUST
            grid[i, j] = hexrgb(c)
    h = 1.5 + 0.13 * len(lab)
    fig, ax = plt.subplots(figsize=(9, h))
    ax.imshow(grid, aspect="auto", interpolation="nearest")
    ax.set_yticks(range(len(lab)))
    ax.set_yticklabels([n[:28] for n in lab["entity_name"]], fontsize=5.5, color=INK2)
    ax.set_xticks([j for j, q in enumerate(qs) if q.quarter == 1])
    ax.set_xticklabels([str(q.year) for q in qs if q.quarter == 1], fontsize=7, color=INK2)
    # Group separators and labels.
    pos = 0
    for k in sorted(order, key=order.get):
        n = int((lab["label"] == k).sum())
        if n == 0:
            continue
        ax.axhline(pos - 0.5, color="white", lw=3)
        ax.text(len(qs) + 0.3, pos + n / 2 - 0.5, f"{titles[k]}\n{n} firms", fontsize=7,
                va="center", color=INK)
        pos += n
    # Lender step-back quarters marked along the top.
    for j, q in enumerate(qs):
        if lender[q]:
            ax.add_patch(plt.Rectangle((j - 0.5, -2.2), 1, 1.2, color=C_SIGNAL, clip_on=False))
    ax.text(-0.5, -2.6, "Quarters when banks were net tightening (lenders step back)", fontsize=7,
            color=INK2, va="bottom")
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (C_NONE, C_SHORT, C_SIGNAL, C_BUST, C_NODATA)]
    ax.legend(handles, ["Cash flow covered capex", "Shortfall (capex > cash flow)",
                        "Signal (shortfall + lenders stepping back)", "Bankruptcy quarter", "No data"],
              loc="upper left", bbox_to_anchor=(0, -0.025), ncol=3, fontsize=7, frameon=False)
    fig.suptitle("Every firm in the test, quarter by quarter (version B, as first reported)",
                 x=0.01, ha="left", fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def rates_figure(results: pd.DataFrame, path: Path):
    head = results[(results["bust"] == "B1") & (results["lender"] == "lender_step_back")
                   & (results["vintage"] == "first") & (results["exits"] == "kept")]
    fig, ax = plt.subplots(figsize=(7, 2.8))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    y = 0
    labels = []
    for r in head.sort_values("version", ascending=False).itertuples():
        for rate, n, color, name in ((r.bust_rate_if_signal, r.TP + r.FP, "#eb6834", "with signal"),
                                     (r.base_rate_no_signal, r.FN + r.TN, "#8a8984", "no signal (base rate)")):
            ax.barh(y, rate * 100, color=color, height=0.7)
            ax.text(rate * 100 + 1, y, f"{rate*100:.0f}%  (n={n})", va="center", fontsize=8, color=INK)
            labels.append(f"Version {r.version}: {name}")
            y += 1
        y += 0.6
    ax.set_yticks([0, 1, 2.6, 3.6][:len(labels)])
    ax.set_yticklabels(labels, fontsize=8, color=INK2)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("% of firms that went bankrupt (8-K Item 1.03), 2013-2019", fontsize=8, color=INK2)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.set_title("Bankruptcy rate with vs without the signal", loc="left", fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    universe = pd.read_csv(DATA_CLEAN / "stage2_universe.csv")
    ttm = pd.read_csv(DATA_CLEAN / "stage2_ttm.csv")
    ttm["quarter"] = pd.PeriodIndex(ttm["quarter"], freq="Q")
    lenders = lender_table()

    events, status = firm_status(universe)
    events.to_csv(DATA_CLEAN / "stage2_bankruptcy_8k_events.csv", index=False)
    status.to_csv(DATA_CLEAN / "stage2_firm_status.csv", index=False)
    status_i = status.set_index("cik")

    results, all_labels = [], []
    grid = itertools.product(["B", "A"], ["B1", "B2"], ["lender_step_back", "baa10y_flag"],
                             ["first", "latest"], ["kept", "dropped"])
    for version, bust, lender, vintage, exits in grid:
        lab = run_variant(universe, status_i, ttm, lenders, version, bust, lender, vintage, exits)
        key = dict(version=version, bust=bust, lender=lender, vintage=vintage, exits=exits)
        results.append({**key, **confusion(lab["label"])})
        all_labels.append(lab.assign(**key))
    results = pd.DataFrame(results)
    labels = pd.concat(all_labels, ignore_index=True)
    results.to_csv(DATA_CLEAN / "stage2_results_all_variants.csv", index=False)
    labels.to_csv(DATA_CLEAN / "stage2_labels_all_variants.csv", index=False)

    FIGURES.mkdir(exist_ok=True)
    head_b = labels[(labels.version == "B") & (labels.bust == "B1") & (labels.lender == "lender_step_back")
                    & (labels.vintage == "first") & (labels.exits == "kept")]
    timeline_figure(head_b, ttm, lenders, FIGURES / "stage2_firm_timeline.png")
    rates_figure(results, FIGURES / "stage2_bust_rates.png")

    # ---- Printed report ------------------------------------------------------
    pd.set_option("display.width", 230); pd.set_option("display.max_rows", 200)
    print(f"Bankruptcy 8-Ks (Item 1.03) found 2013-2019: {len(events)} filings, "
          f"{status['b1_date'].notna().sum()} firms. Exited without bankruptcy: {int(status['exited'].sum())} firms.")
    for v in ("B", "A"):
        r = results[(results.version == v) & (results.bust == "B1") & (results.lender == "lender_step_back")
                    & (results.vintage == "first") & (results.exits == "kept")].iloc[0]
        print(f"\n=== Version {v} | B1 bankruptcy | DRTSCILM | first reported | exits kept ===")
        print(f"                 bust   no bust")
        print(f"  signal        {r.TP:4d}   {r.FP:6d}")
        print(f"  no signal     {r.FN:4d}   {r.TN:6d}      (+{r.untestable} untestable busts)")
        print(f"  n={r.n}; bust rate with signal {r.bust_rate_if_signal:.1%}; base rate (no signal) "
              f"{r.base_rate_no_signal:.1%}; difference {r.difference:+.1%}; Fisher p={r.fisher_p:.3f}")
        print(f"  strict reading: {r.strict_reading}; probabilistic reading: {r.probabilistic_reading}")

    print("\nAll variants (one row each):")
    cols = ["version", "bust", "lender", "vintage", "exits", "n", "TP", "FN", "FP", "TN", "untestable",
            "bust_rate_if_signal", "base_rate_no_signal", "fisher_p", "probabilistic_reading"]
    show = results[cols].copy()
    show["lender"] = show["lender"].map({"lender_step_back": "DRTSCILM", "baa10y_flag": "BAA10Y"})
    for c in ("bust_rate_if_signal", "base_rate_no_signal"):
        show[c] = (show[c] * 100).round(0)
    show["fisher_p"] = show["fisher_p"].round(3)
    print(show.to_string(index=False))

    print("\nHeadline (version B) labels by firm:")
    for k in ("TP", "FN", "untestable", "FP"):
        g = head_b[head_b.label == k]
        print(f"\n{k} ({len(g)}):")
        print(g[["entity_name", "bust_quarter", "first_signal", "reason", "exited"]].to_string(index=False))
    print(f"\nTN ({(head_b.label == 'TN').sum()}): " + "; ".join(head_b[head_b.label == "TN"]["entity_name"]))

    # ---- Outside the pre-registered window (descriptive note only) -----------
    # Firms with no 2013-2019 bankruptcy that filed Item 1.03 in 2020-2021.
    # NOT part of the test: the window was fixed at 2019Q4 in RULE.md.
    post = []
    for r in status[status["b1_date"].isna()].itertuples():
        ev = bankruptcy_events(all_filings(r.cik), start="2020-01-01", end="2021-12-31")
        if not ev.empty:
            e = ev.iloc[0]
            post.append(dict(cik=r.cik, entity_name=r.entity_name, event_date=e["event_date"],
                             accession=e["accessionNumber"], source_url=e["source_url"]))
    post = pd.DataFrame(post)
    post = post.merge(head_b[["cik", "label"]], on="cik", how="left").rename(
        columns={"label": "label_in_headline_test"})
    post.to_csv(DATA_CLEAN / "stage2_post_window_bankruptcies_2020_2021.csv", index=False)
    print("\nOutside the window (not part of the test): Item 1.03 in 2020-2021 among firms with "
          "no 2013-2019 bankruptcy:")
    print(post[["entity_name", "event_date", "label_in_headline_test"]].to_string(index=False))


if __name__ == "__main__":
    main()
