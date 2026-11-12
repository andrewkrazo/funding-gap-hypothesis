# CHANGELOG

Every change to a definition, threshold or universe in `RULE.md` after its first commit
is logged here with the date, the reason, and whether any data had been seen. Results
are reported under both the old and new versions.

## v1.5.1 — 2026-11-12 (version 2 validation; logged BEFORE any test result)
- Fresh sample of 25 v2 cuts (seed 43), judged by hand in
  `data/clean/bbase_validation_precision_v2_reviewed.csv`:
  - **15 clear lender cuts (60%);**
  - 5 still mechanical: wording the filter misses, such as "as a result of the sale,"
    "upon the closing of this transaction," "subsequent to these transactions";
  - 5 unclear.

  Accuracy is 60%, or 75% with the unclear cases set aside: still below 80%.
- Decision: **no further rule changes.** Revising until the check passes would be its own
  forking path. Both versions are run and reported, and the measure is described as noisy.

## v1.5 — 2026-11-12 (addendum A2 validation FAILED; extraction revised; logged BEFORE any test result)
**What the pre-registered validation found** (RULE.md 7.4; judgments in
`data/clean/bbase_validation_precision_reviewed.csv`):
- **Text accuracy is high:** about 23 of 25 sampled sentences really do describe a
  borrowing-base reduction.
- **Accuracy against the thing being measured is not:** only **10 of 25 (40%)** were the
  firm's lenders cutting its credit. 13 were not:
  - 12 mechanical reductions: automatic cuts when the firm issued bonds or did an IPO or
    offering, cuts from selling oil and gas assets, a post-bankruptcy plan;
  - 1 real lender cut retold two years later, so it carried the wrong date.

  2 were unclear.
- That is below the pre-registered 80% bar, so per RULE.md 7.4 the extraction rule is
  revised here and **both versions are reported**.

**Recall check:** 1 of 10 no-cut documents contained a missed cut. Northern Oil's May
2016 redetermination "established" the borrowing base at $350M, with no "reduced to"
wording. Misses like this can only weaken the signal; they can't create false ones. This
is disclosed, not fixed.

**Version 2 of the extraction (`find_cut(..., strict=True)`):**
1. A sentence is excluded if it mentions a mechanical trigger: issuing or offering notes
   or shares, an IPO, an asset sale, divestiture or disposition, an "automatic"
   reduction, or a bankruptcy plan or emergence.
2. Duplicates: the same new amount (within 1%) is the same cut **whenever** it is retold
   (v1 used a 270-day limit). The earliest filing still dates the cut.
3. Amounts under $1 million are discarded as parsing errors.

**Validating v2:** a **fresh** random sample of 25 v2 cuts (seed 43) is checked by hand
before the test is run. Re-checking the old sample would be circular, since it was used
to design v2. If v2 is still below 80%, both versions are still reported and the
shortfall is stated plainly.

## v1.4.1 — 2026-11-12 (data-collection bug fix; no rule change; no results had been looked at)
- The first borrowing-base download passed the form filter
  "10-K,10-Q,8-K,10-K/A,10-Q/A,8-K/A" to EDGAR full-text search. That list makes the
  search return mostly amended filings: 133 filings from 52 firms, against 76 firms found
  in the feasibility count. Using "10-K,10-Q,8-K", which already includes amendments,
  fixes it (checked on SandRidge: 86 documents instead of 5).
- The download was deleted and redone. The extraction rules (`find_cut`) are unchanged.
  The only thing seen from the bad download was its summary counts (43 cut sentences,
  26 cuts at 13 firms); no labels or results.

## v1.4 — 2026-11-12 (addendum A2; logged BEFORE the borrowing-base data is pulled)
- Added RULE.md section 7: a follow-up test with a **firm-level** lender measure (cuts
  to each firm's borrowing base, read from its own filings). Definitions, extraction
  rule, comparisons, validation and reading were fixed before any borrowing-base data
  was downloaded.
- Seen beforehand (disclosed in RULE.md 7): bankruptcy outcomes from the main test, and a
  count of which firms mention a borrowing base at all.

## v1.3 — 2026-11-12 (peer review; made AFTER results were seen, so everything is reported both ways)
- **Data correction:** Black Elk's 8-K (accession 0001518909-14-000034) is listed in
  EDGAR's index metadata as Item 1.03, but the document reports only Items 5.02/9.01 (an
  officer's resignation). It is no longer counted as a bankruptcy (`MISTAGGED_1_03` in
  `fundgap/busts.py`). This applies the pre-registered definition (an 8-K *reporting*
  Item 1.03) more faithfully. Headline before → after: 30% vs 53% (p = 0.10) → 30% vs 47%
  (p = 0.18). Reading unchanged. The other 31 bankruptcy 8-Ks were read and confirmed.
- **Clearer miss reasons:** the code now says whether lenders never tightened in the
  window, the firm had no data while they did, a shortfall never coincided with
  tightening, or there was no shortfall. Labels unchanged.
- **Post-hoc checks added** (`stage2b_test.py`, `*_posthoc_checks.csv`), never headlined:
  signal public before the bankruptcy (ALFRED first-release dates + filing dates); two
  symmetric-window versions; dropping firms that could never have signaled; counting EPL
  Oil & Gas as bankrupt. All read "not supported."
- **Guard:** stage 2B stops if the bank survey has any gap in 2012–2019, instead of reading
  a gap as "no step-back."
- **Bug fix (code only):** the bankruptcy reader failed for firms with no 8-Ks at all
  (foreign filers).
- **Disclosures added to RESULTS.md:** non-independence of firms (p-values overstate the
  evidence); bankruptcies outside the 8-K measure (EPL, Samson, Black Elk); producers
  outside SIC 1311 (Energy XXI, Atlas); exclusions that line up with outcomes;
  2014-IPO selection; Google dominating the comparison sector; remaining 10-K/10-Q tag
  mixing in the TTM method.
- An earlier "signal at least 2 quarters before the bust" check was superseded by the
  publication-date check. It was over-strict: two signals were public before their
  firms' bankruptcies but fell less than 2 quarters before them.

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
