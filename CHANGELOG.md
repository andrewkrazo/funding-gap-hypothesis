# CHANGELOG

Every change to a definition, threshold or universe in `RULE.md` after its first commit
is logged here with the date, the reason, and whether any data had been seen. Results
are reported under both the old and new versions.

## Data-exposure note — 2026-11-12 (Stage 1)
- Stage 1 downloaded the full DRTSCILM and BAA10Y histories, so the lender-proxy values
  for the Stage 2 window (2013-2016) have now been seen. No EDGAR data for the Stage 2
  energy universe has been downloaded. No definitions or thresholds changed.
- Observation, recorded here so it can't be quietly fixed later: DRTSCILM > 0 was true in
  28 of 47 quarters from 2015Q1 to 2026Q3, so the pre-registered "lenders step back" flag
  is on more often than off. That makes it a loose filter. The threshold stays as
  pre-registered; this weakness will be reported with the Stage 2 results.
- Data mapping (not a rule change): Microsoft and Oracle filed operating cash flow for
  roughly FY2013-FY2018 under the fallback tag RULE.md 2.2 already lists. Amazon's capex
  tag change and missing quarters are recorded in data/tag_map.csv; the series are left
  unspliced pending the author's decision.

## v1.0.1 — 2026-11-12 (citation only, no data seen)
- Filled in the source for Dalio's "bubbles burst when holders must sell to raise cash"
  idea: Forbes, Oct 7, 2026 (Fiona Riley), reporting his Singapore conference remarks.
- Confirmed the essay date shown on the Substack page: June 10, 2026.
- No definitions, thresholds or universes changed.

## v1.0 — 2026-11-12
- Initial pre-registration. No data downloaded.
- Design choices made by the author before the commit: lender proxy = FRED DRTSCILM;
  two-tier bust definition (B1 bankruptcy primary, B2 bankruptcy or capex cut as
  secondary); universe size cut = assets ≥ $500M at year-end 2013.
- Departure from the original brief, with reason: the Stage 2 data period runs to
  2019Q4, not 2018, so that every possible signal (through 2016Q4) has a full 3-year
  window in which a bust could appear.
