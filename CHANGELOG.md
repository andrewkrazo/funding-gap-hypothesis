# CHANGELOG

Every change to a definition, threshold or universe in `RULE.md` after its first commit
is logged here with the date, the reason, and whether any data had been seen. Results
are reported under both the old and new versions.

## v1.2 — 2026-11-12 (addendum A1; logged BEFORE the comparison sector's data is pulled)
- Added RULE.md section 6: the "booms that ended well" comparison group, chosen
  mechanically as the largest non-energy capex boom of 2011→2014, so it isn't picked on
  its outcome. No existing definitions, thresholds or results changed.
- Prior knowledge, disclosed: I know the general history of several sectors. The rule
  ranks sectors by capex growth alone, and I don't know in advance which one it will pick.

## v1.1 — 2026-11-12 (Stage 2 data step; logged BEFORE any bust/bankruptcy data was downloaded)

Stage 2 company cash-flow data revealed three problems the pre-registration did not
anticipate. Each is corrected below. Stage 2 is reported in **two complete versions**:

- **Version A, as pre-registered:** quarter-by-quarter differencing summed into
  trailing four quarters, capex rule exactly as written, all mechanically selected firms.
- **Version B, corrected:** the three changes below.

Both versions are run through the identical test and both are reported. Neither the
thresholds nor the definitions of shortfall, lender step-back, signal or bust change.

1. **How trailing-four-quarter (TTM) totals are computed.** Many producers built capex
   from one set of XBRL tags in their 10-Qs and another in their 10-K. Subtracting
   year-to-date figures across those filings produced impossible values: Chesapeake
   (CIK 895126) shows −$2.9B of capex in 2012Q3. Version B computes TTM with the standard
   identity *last fiscal year (10-K) + year-to-date − same period a year earlier*, where
   the last two figures come from the same 10-Q and so always share tags. With
   consistent data the two methods agree exactly (unit-tested). On real data the
   yes/no shortfall answer agrees in all quarters for the median firm.
   Rejected alternative: treating mismatched quarters as missing. It would have removed
   30% of measurable firm-quarters and 13 firms.
2. **Subtotal double-counting.** RULE.md 2.3 sums candidate tags when no total tag is
   reported. Some firms (Antero, Resolute, Kosmos) report a line that equals the sum of
   the others, i.e. a total, so summing double-counts. Version B uses such a tag alone,
   the same logic as RULE.md 2.3 step 1. Detection is mechanical: one tag equals the sum
   of the rest within 1%.
3. **Parent and subsidiary both in the universe.** EP Energy LLC (CIK 1555082) is "a
   wholly-owned subsidiary of EP Energy Corporation" (CIK 1584952), per its FY2017 10-K
   (accession 0001555082-18-000002). Counting both would count one company twice.
   Version B drops the subsidiary. How it was found: pairs with 2013 assets within 1%
   were screened, then confirmed in the filing text. Assets alone were not used, because
   unrelated firms can match closely (W&T Offshore vs Ranger Oil differ by 0.009%).
   No pair shared a filing accession number (no joint filers).

4. **Clarification (both versions): busts the data can't judge.** RULE.md §4 calls a
   bust a miss (FN) when no signal occurred in the 12 quarters before it. If **none** of
   those 12 quarters has a measurable shortfall value, the data can't say whether cash
   flow covered spending, so the firm is labeled *untestable*, kept out of the 2×2, and
   counted and named in the results. Busts with some measurable quarters but no signal
   stay FN, split by reason: no shortfall, or shortfall without lender step-back.
5. **Clarification (both versions): what "exited" means.** A firm with no Item 1.03 8-K
   whose last 10-K/10-Q was filed before 2019-10-01 stopped reporting before follow-up
   ended (for example, it was acquired). It counts as no bust in the main table and is
   dropped in the RULE.md §4 sensitivity table.

**Deviation, stated plainly:** RULE.md 2.3 step 3 says firms failing the
"capex ≤ investing outflows" check are reviewed by hand. The check flags 80+ firm-years,
mostly in years with large asset sales whose proceeds use company-specific tags the check
can't see, so a by-hand review of each was not done. The direct double-count test
(item 2) replaces it for the failure the check was meant to catch. Every flagged year is
listed in `data/clean/stage2_investing_flags.csv`.

**Known, not corrected:** a few firms carry SIC 1311 but are not producers (for example
midstream partnerships, a refiner, an oilfield-services firm). The pre-registered
universe keeps them, since removing them would take judgment, and they are named in the
results.

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
