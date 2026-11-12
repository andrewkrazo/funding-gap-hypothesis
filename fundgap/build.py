"""Build per-company quarterly and trailing-four-quarter tables from EDGAR facts."""

from __future__ import annotations

import pandas as pd

from . import edgar
from .quarterly import to_quarterly, trailing_four


def tag_facts(ciks: list[int], tag: str) -> pd.DataFrame:
    """Facts for one tag, pooled across one or more CIKs.

    Pooling is for the same company filing under more than one SEC identity,
    e.g. Google Inc. (CIK 1288776) before it became Alphabet (CIK 1652044).
    """
    frames = [edgar.facts_for_tag(edgar.companyfacts(c), tag) for c in ciks]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return edgar.facts_for_tag({"cik": ciks[0], "facts": {}}, tag)
    return pd.concat(frames, ignore_index=True)


def priority_facts(ciks: list[int], tags: list[str]) -> pd.DataFrame:
    """Facts from several tags for the SAME line item, in priority order.

    If one filing reports the same period under two of the tags, the earlier
    tag in the list wins. This implements the fallback order in RULE.md 2.2.
    Only use it for tags that measure the same line (checked before use).
    """
    pooled = []
    for rank, tag in enumerate(tags):
        f = tag_facts(ciks, tag)
        if not f.empty:
            pooled.append(f.assign(tag_rank=rank))
    if not pooled:
        return tag_facts(ciks, tags[0])
    df = pd.concat(pooled, ignore_index=True).sort_values("tag_rank")
    return df.drop_duplicates(["start", "end", "accn"], keep="first")


def quarterly_series(ciks: list[int], tag: str | list[str],
                     mode: str = "first") -> pd.DataFrame:
    """True quarterly values for one tag (or a priority list of tags for the
    same line), with a link to each source filing."""
    tags = [tag] if isinstance(tag, str) else list(tag)
    facts = priority_facts(ciks, tags)
    tag_by_accn = facts.groupby("accn")["tag"].first().to_dict()
    q = to_quarterly(facts, mode=mode)
    if q.empty:
        return q
    cik_by_accn = dict(zip(facts["accn"], facts["cik"]))
    q["source_urls"] = q["accn"].map(
        lambda accns: " ".join(edgar.filing_index_url(cik_by_accn[a], a)
                               for a in accns.split("|")))
    q["tag"] = q["accn"].map(lambda accns: "|".join(
        sorted({tag_by_accn[a] for a in accns.split("|")})))
    q["vintage"] = mode
    return q


def coverage(q: pd.DataFrame, first: str, last: str) -> list[str]:
    """Calendar quarters in [first, last] with no value (reported, never filled)."""
    want = pd.period_range(first, last, freq="Q")
    have = set(q["quarter"]) if not q.empty else set()
    return [str(p) for p in want if p not in have]


def ttm(q: pd.DataFrame) -> pd.Series:
    return trailing_four(q) if not q.empty else pd.Series(dtype=float)
