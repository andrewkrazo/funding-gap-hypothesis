"""Addendum A2, part A: collect borrowing-base sentences, extract cuts, and draw
the pre-registered validation samples (RULE.md section 7).

Outputs:
    data/raw/edgar/borrowing_base_sentences.jsonl.gz   every 'borrowing base' sentence (cached)
    data/clean/bbase_cuts_all_{v1,v2}.csv             every sentence each rule version calls a cut
    data/clean/bbase_cuts_{v1,v2}.csv                 distinct cuts (duplicates removed)
    data/clean/bbase_validation_precision_{v1,v2}.csv 25 random cuts to check by hand
    (v1 = pre-registered rules; v2 = revised after validation, CHANGELOG v1.5)
    data/clean/bbase_validation_recall.csv            10 random no-cut documents to read
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from fundgap.bbase import collect_sentences, dedupe_cuts, find_cut
from fundgap.config import DATA_CLEAN

SEED = 42


def main():
    lab = pd.read_csv(DATA_CLEAN / "stage2_labels_all_variants.csv")
    firms = sorted(lab[lab["version"] == "B"]["cik"].unique())
    sents = collect_sentences([int(c) for c in firms])
    sents = sents.dropna(subset=["sentence"])
    print(f"Sentences: {len(sents)} from {sents['adsh'].nunique()} filings, {sents['cik'].nunique()} firms")

    for version, strict, window, seed in (("v1", False, 270, SEED), ("v2", True, None, SEED + 1)):
        rows = []
        for r in sents.itertuples():
            c = find_cut(r.sentence, strict=strict)
            if c:
                rows.append(dict(cik=r.cik, file_date=r.file_date, form=r.form, adsh=r.adsh, url=r.url,
                                 new=c["new"], old=c["old"], rule=c["rule"], sentence=r.sentence))
        cuts_all = pd.DataFrame(rows)
        cuts_all.to_csv(DATA_CLEAN / f"bbase_cuts_all_{version}.csv", index=False)
        cuts = pd.concat([dedupe_cuts(g, window_days=window) for _, g in cuts_all.groupby("cik")],
                         ignore_index=True)
        cuts.to_csv(DATA_CLEAN / f"bbase_cuts_{version}.csv", index=False)
        print(f"[{version}] sentences called a cut: {len(cuts_all)}; distinct cuts: {len(cuts)} "
              f"at {cuts['cik'].nunique()} firms")
        # Pre-registered validation samples, drawn without looking at outcomes.
        # v1: seed 42 (RULE.md 7.4). v2: a fresh draw, seed 43 (CHANGELOG v1.5).
        pool = cuts if version == "v2" else cuts_all
        pool.sample(n=min(25, len(pool)), random_state=seed).to_csv(
            DATA_CLEAN / f"bbase_validation_precision_{version}.csv", index=False)
        if version == "v1":
            docs_with_cut = set(cuts_all["adsh"])
            no_cut_docs = sents[~sents["adsh"].isin(docs_with_cut)].drop_duplicates("adsh")
            picked = no_cut_docs.sample(n=min(10, len(no_cut_docs)), random_state=SEED)["adsh"]
            sents[sents["adsh"].isin(picked)].to_csv(DATA_CLEAN / "bbase_validation_recall.csv", index=False)
    print("Validation samples written.")


if __name__ == "__main__":
    main()
