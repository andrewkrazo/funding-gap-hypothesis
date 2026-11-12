# The Funding-Gap Hypothesis

A small, pre-registered pilot test of one rule about building booms:

> *A building boom ends in a bust when builders' cash flow falls short of their spending
> and lenders step back.*

*Author: Andrew Razo.*

**Status: Stage 1 (descriptive) built and awaiting review. Stage 2 (the actual test) not started.**

## Rerun Stage 1
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows path; use .venv/bin on Mac/Linux
export SEC_USER_AGENT="Your Name your@email.com"   # required by the SEC
export FRED_API_KEY="..."                         # free key from fred.stlouisfed.org
python -m pytest                                  # unit tests for the YTD -> quarterly logic
python stages/stage1_hyperscalers.py              # rebuilds data/clean/ and figures/
```
Raw downloads are cached in `data/raw/` and logged with URL, time and SHA-256 in
`data/raw/SOURCES.csv`. Delete `data/raw/` to re-download. EDGAR updates as new filings
arrive, so fresh pulls will include later quarters.

- [`RULE.md`](RULE.md): the exact definitions, universes, test, and failure
  conditions, committed before any data work.
- [`CHANGELOG.md`](CHANGELOG.md): every later change to those definitions, with reasons.

Data, method, results and limitations will be added in later stages. This is a small
pilot, not proof.
