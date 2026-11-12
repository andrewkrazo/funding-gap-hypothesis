"""Stage 1 (descriptive only): capex vs operating cash flow for five large
cloud/AI spenders, alongside the lender-conditions proxies.

Nothing here is a prediction. None of these companies has busted, so this
stage only shows where each stands against the rule's conditions.

Run:  python stages/stage1_hyperscalers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from fundgap import build
from fundgap.config import DATA_CLEAN, FIGURES, ROOT
from fundgap.lenders import lender_table

FIRST_Q, LAST_Q = "2015Q1", "2026Q3"
VINTAGES = ["first", "latest"]

# Palette: validated reference categorical slots (dataviz skill, light mode).
OCF_COLOR, CAPEX_COLOR, MUTED = "#2a78d6", "#eb6834", "#8a8984"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"


def load_tag_map() -> pd.DataFrame:
    tm = pd.read_csv(ROOT / "data" / "tag_map.csv")
    return tm[tm["stage"] == 1]


def build_quarterly() -> pd.DataFrame:
    rows = []
    for r in load_tag_map().itertuples():
        ciks = [int(c) for c in str(r.ciks).split("|")]
        tags = r.tags_in_priority_order.split("|")
        for vintage in VINTAGES:
            q = build.quarterly_series(ciks, tags, vintage)
            if q.empty:
                continue
            q.insert(0, "series", r.series)
            q.insert(0, "company", r.company)
            rows.append(q)
    return pd.concat(rows, ignore_index=True)


def build_ttm(quarterly: pd.DataFrame, lenders: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (company, vintage), g in quarterly.groupby(["company", "vintage"]):
        ocf = build.ttm(g[g["series"] == "ocf"])
        capex_series = [s for s in g["series"].unique() if s.startswith("capex")]
        for cs in capex_series:
            capex = build.ttm(g[g["series"] == cs])
            df = pd.DataFrame({"ttm_ocf": ocf, "ttm_capex": capex})
            df.index.name = "quarter"
            df = df.reset_index()
            df["company"], df["vintage"], df["capex_definition"] = company, vintage, cs
            out.append(df)
    t = pd.concat(out, ignore_index=True)
    t = t[(t["quarter"] >= pd.Period(FIRST_Q)) & (t["quarter"] <= pd.Period(LAST_Q))]
    both = t["ttm_capex"].notna() & t["ttm_ocf"].notna()
    t["capex_to_ocf"] = (t["ttm_capex"] / t["ttm_ocf"]).where(both)
    t["shortfall"] = (t["ttm_capex"] > t["ttm_ocf"]).astype("boolean").where(both)
    t = t.merge(lenders[["lender_step_back", "drtscilm"]], left_on="quarter",
                right_index=True, how="left")
    t["both_conditions"] = (t["shortfall"] & t["lender_step_back"].astype("boolean"))
    cols = ["company", "capex_definition", "vintage", "quarter", "ttm_capex", "ttm_ocf",
            "capex_to_ocf", "shortfall", "drtscilm", "lender_step_back", "both_conditions"]
    return t[cols].sort_values(["company", "capex_definition", "vintage", "quarter"])


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def to_ts(periods):
    return [p.end_time for p in periods]


def fig_capex_vs_ocf(ttm: pd.DataFrame, path: Path):
    t = ttm[ttm["vintage"] == "first"]
    companies = ["Amazon", "Microsoft", "Alphabet", "Meta", "Oracle"]
    fig, axes = plt.subplots(5, 1, figsize=(8, 12), sharex=True)
    for ax, company in zip(axes, companies):
        g = t[t["company"] == company]
        style(ax)
        ocf = g.drop_duplicates("quarter").set_index("quarter")["ttm_ocf"] / 1e9
        ax.plot(to_ts(ocf.index), ocf.values, color=OCF_COLOR, lw=2, label="Operating cash flow")
        for cs, gg in g.groupby("capex_definition"):
            s = gg.set_index("quarter")["ttm_capex"] / 1e9
            dashed = cs == "capex_net_old"
            ax.plot(to_ts(s.index), s.values, color=CAPEX_COLOR, lw=2,
                    ls="--" if dashed else "-",
                    label="Capex (old net-of-incentives definition)" if dashed else "Capex")
            short = gg[gg["shortfall"] == True]
            for q in short["quarter"]:
                ax.axvspan(q.start_time, q.end_time, color=CAPEX_COLOR, alpha=0.12, lw=0)
        ax.set_title(company, loc="left", fontsize=10, color=INK, fontweight="bold")
        ax.set_ylabel("$ billions, trailing 4Q", fontsize=8, color=INK2)
        ax.legend(loc="upper left", fontsize=7, frameon=False)
    fig.suptitle("Capex vs operating cash flow (trailing four quarters, as first reported)\n"
                 "Shaded quarters: capex exceeded operating cash flow (the RULE.md 'shortfall')",
                 fontsize=10, color=INK, x=0.02, ha="left")
    fig.text(0.02, 0.005, "Source: SEC EDGAR XBRL companyfacts; see data/clean/stage1_quarterly.csv "
             "for the accession number behind every value.", fontsize=7, color=INK2)
    fig.tight_layout(rect=(0, 0.01, 1, 0.97))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_ratio(ttm: pd.DataFrame, path: Path):
    t = ttm[(ttm["vintage"] == "first") & (ttm["capex_definition"] != "capex_net_old")]
    companies = ["Amazon", "Microsoft", "Alphabet", "Meta", "Oracle"]
    fig, axes = plt.subplots(1, 5, figsize=(12, 3.2), sharex=True, sharey=True)
    for ax, company in zip(axes, companies):
        style(ax)
        g = t[t["company"] == company].dropna(subset=["capex_to_ocf"])
        ax.axhline(1.0, color=INK2, lw=1, ls=":")
        ax.plot(to_ts(g["quarter"]), g["capex_to_ocf"], color=CAPEX_COLOR, lw=2)
        if not g.empty:
            last = g.iloc[-1]
            ax.annotate(f"{last['capex_to_ocf']:.2f}", (last["quarter"].end_time, last["capex_to_ocf"]),
                        textcoords="offset points", xytext=(-4, 6), ha="right", fontsize=8, color=INK)
        ax.set_title(company, fontsize=9, color=INK, loc="left")
        ax.tick_params(axis="x", rotation=45)
    axes[0].set_ylabel("Capex / operating cash flow", fontsize=8, color=INK2)
    fig.suptitle("Capex as a multiple of operating cash flow (trailing 4Q). Above the dotted line = shortfall.",
                 fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_lenders(lenders: pd.DataFrame, path: Path):
    l = lenders.loc[pd.Period(FIRST_Q):pd.Period(LAST_Q)]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    style(a1); style(a2)
    x = to_ts(l.index)
    colors = [CAPEX_COLOR if v > 0 else MUTED for v in l["drtscilm"]]
    a1.bar(x, l["drtscilm"], width=60, color=colors)
    a1.axhline(0, color=INK2, lw=1)
    a1.set_title("Banks tightening loan standards, net % (FRED DRTSCILM). "
                 "Orange = above 0 = 'lenders step back'", loc="left", fontsize=9, color=INK)
    a2.plot(x, l["baa10y_qavg"], color=OCF_COLOR, lw=2, label="Quarterly average")
    a2.plot(x, l["baa10y_trailing20_median"], color=MUTED, lw=1.5, ls="--",
            label="Median of previous 20 quarters")
    a2.set_title("Side check: Baa corporate yield minus 10-yr Treasury, percentage points (FRED BAA10Y)",
                 loc="left", fontsize=9, color=INK)
    a2.legend(fontsize=7, frameon=False)
    fig.text(0.01, 0.005, "Survey readings are placed in the quarter they describe "
             "(survey dated the start of the next quarter).", fontsize=7, color=INK2)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    DATA_CLEAN.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    lenders = lender_table()
    quarterly = build_quarterly()
    ttm = build_ttm(quarterly, lenders)

    quarterly.to_csv(DATA_CLEAN / "stage1_quarterly.csv", index=False)
    ttm.to_csv(DATA_CLEAN / "stage1_ttm.csv", index=False)
    lenders.loc[pd.Period("2010Q1"):].to_csv(DATA_CLEAN / "lender_proxies.csv")

    fig_capex_vs_ocf(ttm, FIGURES / "stage1_capex_vs_ocf.png")
    fig_ratio(ttm, FIGURES / "stage1_capex_to_ocf.png")
    fig_lenders(lenders, FIGURES / "stage1_lender_proxies.png")

    # ---- Printed summary -------------------------------------------------
    pd.set_option("display.width", 200)
    t = ttm[(ttm["vintage"] == "first")]
    print("\nLatest quarter, as first reported ($ billions, trailing four quarters):")
    latest = t.dropna(subset=["capex_to_ocf"]).groupby(["company", "capex_definition"]).tail(1)
    show = latest[["company", "capex_definition", "quarter", "ttm_capex", "ttm_ocf", "capex_to_ocf", "shortfall"]].copy()
    show[["ttm_capex", "ttm_ocf"]] = (show[["ttm_capex", "ttm_ocf"]] / 1e9).round(1)
    show["capex_to_ocf"] = show["capex_to_ocf"].round(2)
    print(show.to_string(index=False))

    print("\nQuarters with a shortfall, 2015Q1-2026Q3 (as first reported):")
    for (c, cs), g in t.groupby(["company", "capex_definition"]):
        valid = g.dropna(subset=["shortfall"])
        sq = [str(q) for q in valid.loc[valid["shortfall"] == True, "quarter"]]
        print(f"  {c:9} {cs:16} {len(sq)} of {len(valid)} measurable quarters: {', '.join(sq) or 'none'}")

    l = lenders.loc[pd.Period(FIRST_Q):pd.Period(LAST_Q)]
    on = [str(q) for q in l.index[l["lender_step_back"] == True]]
    print(f"\nLender step-back (DRTSCILM > 0) quarters, {FIRST_Q}-{LAST_Q}: {len(on)} of {len(l)}: {', '.join(on)}")

    print("\nQuarters with BOTH conditions (descriptive, not a prediction):")
    both = t[t["both_conditions"] == True]
    print(both[["company", "capex_definition", "quarter", "drtscilm"]].to_string(index=False)
          if not both.empty else "  none")

    f, la = ttm[ttm["vintage"] == "first"], ttm[ttm["vintage"] == "latest"]
    m = f.merge(la, on=["company", "capex_definition", "quarter"], suffixes=("_f", "_l"))
    m = m.dropna(subset=["shortfall_f", "shortfall_l"])
    changed = m[m["shortfall_f"] != m["shortfall_l"]]
    print(f"\nFirst-reported vs latest-filed: shortfall flag differs in {len(changed)} "
          f"of {len(m)} company-quarters.")
    if not changed.empty:
        print(changed[["company", "capex_definition", "quarter", "capex_to_ocf_f", "capex_to_ocf_l"]].to_string(index=False))


if __name__ == "__main__":
    main()
