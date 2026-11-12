"""Firm-level "lenders step back": borrowing-base cuts read from SEC filings
(RULE.md section 7, addendum A2).

Plain-language background: many oil and gas producers borrow under a credit
line whose maximum size (the "borrowing base") the banks re-set about twice a
year from the value of the firm's oil and gas reserves. When the banks cut it,
the firm must disclose that. A cut is the firm's own lenders stepping back.

This file:
  1. finds each firm's filings that mention "borrowing base" (EDGAR full-text search),
  2. keeps only the sentences that mention it,
  3. decides, with fixed rules, whether a sentence reports a cut and to what amount,
  4. turns cuts into a quarter-by-quarter yes/no flag.
The rules in step 3 were written and unit-tested before any real filing was read.
"""

from __future__ import annotations

import gzip
import html
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

from .config import DATA_RAW, sec_user_agent

SENTENCES_FILE = DATA_RAW / "edgar" / "borrowing_base_sentences.jsonl.gz"
EFTS = "https://efts.sec.gov/LATEST/search-index"
# Listing amended forms ("10-K/A") in the filter breaks the search (it then returns
# mostly amendments); the plain list already returns amendments too. See CHANGELOG v1.4.1.
FORMS = "10-K,10-Q,8-K"

# ---------------------------------------------------------------------------
# Step 3: the frozen rules
# ---------------------------------------------------------------------------

MONEY = r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(billion|million|thousand)?"
VERB = r"(?:reduced|decreased|lowered|declined|cut)"
AUX = r"(?:was|were|has been|have been|had been|will be|is|are|being)"
# Case-sensitive on purpose: the month "May" must not read as the word "may".
HYPOTHETICAL = re.compile(r"\b(could|may|might|would|should|[Ii]f|[Uu]nless|whether|potential(ly)?)\b")
VOLUNTARY = re.compile(r"\b(elect(ed|s|ion)?|at (our|its|the company.s) request|request(ed)? by (us|the company)|voluntar(y|ily))\b", re.I)

# 1. "the borrowing base was reduced (from $X) to $Y" / "...decreased to $Y"
P_REDUCED_TO = re.compile(
    r"borrowing base\b.{0,120}?\b(?:" + AUX + r"\s+)?(?:\w+\s+){0,2}?" + VERB + r"\b(?P<mid>.{0,100}?)\bto\s+" + MONEY,
    re.I)
# 2. "the lenders reduced the borrowing base (from $X) to $Y"
P_LENDERS_REDUCED = re.compile(
    r"\b" + VERB + r"\s+(?:the|our|its|their)?\s*(?:\w+\s+){0,3}?borrowing base\b(?P<mid>.{0,100}?)\bto\s+" + MONEY,
    re.I)
# 3. "borrowing base ... from $X to $Y" (counts only if Y < X)
P_FROM_TO = re.compile(
    r"borrowing base\b.{0,150}?\bfrom\s+" + MONEY + r"\s+to\s+" + MONEY, re.I)


def to_dollars(number: str, unit: str | None) -> float:
    v = float(number.replace(",", ""))
    return v * {"billion": 1e9, "million": 1e6, "thousand": 1e3}.get((unit or "").lower(), 1.0)


def _from_amount(mid: str) -> float | None:
    m = re.search(r"\bfrom\s+" + MONEY, mid, re.I)
    return to_dollars(m.group(1), m.group(2)) if m else None


# Version 2 (CHANGELOG v1.5): reductions with a mechanical trigger are not lenders
# stepping back. Most common: loan agreements that automatically shrink the borrowing
# base when the firm issues bonds, and cuts that follow selling oil and gas assets.
MECHANICAL = re.compile(
    r"\b(issu(e|ed|ance|ing)|offering|notes?\b|initial public|IPO|divest\w*|dispos\w*|"
    r"sale of|sold|automatic(ally)?|plan of reorganization|the Plan\b|emergence|chapter 11)",
    re.I)
MIN_AMOUNT = 1e6  # a borrowing base under $1 million is a parsing error


def find_cut(sentence: str, strict: bool = False) -> dict | None:
    """Return {'new': $, 'old': $ or None, 'rule': id} if the sentence reports a
    borrowing-base cut by lenders, else None.

    strict=False is version 1 (pre-registered). strict=True is version 2, which
    also excludes mechanical reductions and impossible amounts (CHANGELOG v1.5)."""
    s = re.sub(r"\s+", " ", sentence)
    if "borrowing base" not in s.lower() or VOLUNTARY.search(s):
        return None
    if strict and MECHANICAL.search(s):
        return None
    c = _find_cut_v1(s)
    if strict and c is not None and c["new"] < MIN_AMOUNT:
        return None
    return c


def _find_cut_v1(s: str) -> dict | None:
    # Rule 3 first: an explicit "from $X to $Y" decides direction unambiguously.
    for m in P_FROM_TO.finditer(s):
        old = to_dollars(m.group(1), m.group(2))
        new = to_dollars(m.group(3), m.group(4))
        if new < old and not HYPOTHETICAL.search(s[max(0, m.start() - 60):m.start() + 60]):
            return dict(new=new, old=old, rule="from_to")
    for rule, pat in (("reduced_to", P_REDUCED_TO), ("lenders_reduced", P_LENDERS_REDUCED)):
        for m in pat.finditer(s):
            window = s[max(0, m.start() - 60):m.end()]
            if HYPOTHETICAL.search(window):
                continue
            new = to_dollars(m.group(len(m.groups()) - 1), m.group(len(m.groups())))
            old = _from_amount(m.group("mid"))
            if old is not None and new >= old:
                continue  # that was an increase
            return dict(new=new, old=old, rule=rule)
    return None


# ---------------------------------------------------------------------------
# Step 4: cuts -> quarterly flag
# ---------------------------------------------------------------------------

def dedupe_cuts(cuts: pd.DataFrame, window_days: int | None = 270) -> pd.DataFrame:
    """One row per distinct cut: the same new amount (within 1%) reported again
    is the same cut. Keeps the earliest public report.
    window_days=270 is version 1; None (any time later) is version 2."""
    if cuts.empty:
        return cuts
    cuts = cuts.sort_values("file_date")
    kept = []
    for r in cuts.itertuples():
        d = pd.Timestamp(r.file_date)
        dup = any(abs(r.new - k.new) <= 0.01 * k.new and
                  (window_days is None or (d - pd.Timestamp(k.file_date)).days <= window_days)
                  for k in kept)
        if not dup:
            kept.append(r)
    return pd.DataFrame(kept).drop(columns=["Index"], errors="ignore")


def firm_flag(cuts: pd.DataFrame, quarters: pd.PeriodIndex) -> pd.Series:
    """True in the quarter a cut was first reported and the quarter after."""
    flag = pd.Series(False, index=quarters)
    for d in cuts["file_date"] if not cuts.empty else []:
        q = pd.Period(pd.Timestamp(d), freq="Q")
        for qq in (q, q + 1):
            if qq in flag.index:
                flag[qq] = True
    return flag


# ---------------------------------------------------------------------------
# Steps 1-2: finding filings and keeping the relevant sentences
# ---------------------------------------------------------------------------

def _get(url, params=None, tries=4):
    last = None
    for k in range(tries):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": sec_user_agent()}, timeout=90)
            time.sleep(0.15)
            if r.status_code == 200:
                return r
            last = f"status {r.status_code}"
        except requests.exceptions.RequestException as e:  # dropped connection, timeout
            last = repr(e)
        time.sleep(5 * (k + 1))
    raise RuntimeError(f"Download failed ({last}) for {url}")


def search_documents(cik: int, start="2012-01-01", end="2019-12-31") -> list[dict]:
    """Every document in the firm's own filings that contains 'borrowing base'."""
    out, frm = [], 0
    while True:
        r = _get(EFTS, params={"q": '"borrowing base"', "dateRange": "custom", "startdt": start,
                               "enddt": end, "ciks": f"{int(cik):010d}", "forms": FORMS, "from": frm})
        j = r.json()
        if "hits" not in j:  # occasional error payload: wait and retry this page
            time.sleep(3)
            continue
        hits = j["hits"]["hits"]
        for h in hits:
            adsh, fname = h["_id"].split(":", 1)
            src = h["_source"]
            out.append(dict(cik=int(cik), adsh=adsh, filename=fname, form=src.get("form"),
                            file_date=src.get("file_date")))
        if len(hits) < 100:
            return out
        frm += 100


def sentences_in(doc: dict) -> list[str]:
    url = (f"https://www.sec.gov/Archives/edgar/data/{doc['cik']}/"
           f"{doc['adsh'].replace('-', '')}/{doc['filename']}")
    raw = _get(url).text
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[.;])\s+(?=[A-Z(\"“])", text)
    return url, [p.strip() for p in parts if "borrowing base" in p.lower() and len(p) < 2000]


def collect_sentences(ciks: list[int], path: Path = SENTENCES_FILE) -> pd.DataFrame:
    """Download (once) and cache every 'borrowing base' sentence for these firms."""
    done = set()
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                done.add(json.loads(line)["cik"])
    path.parent.mkdir(parents=True, exist_ok=True)
    for i, cik in enumerate(c for c in ciks if c not in done):
        rows = []
        for doc in search_documents(cik):
            url, sents = sentences_in(doc)
            for s in sents:
                rows.append({**doc, "url": url, "sentence": s})
        if not rows:  # remember firms with no matches, so they aren't searched again
            rows = [dict(cik=int(cik), adsh=None, filename=None, form=None, file_date=None,
                         url=None, sentence=None)]
        with gzip.open(path, "at", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        print(f"  firm {cik}: {sum(r['sentence'] is not None for r in rows)} sentences", flush=True)
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return pd.DataFrame([json.loads(l) for l in f])
