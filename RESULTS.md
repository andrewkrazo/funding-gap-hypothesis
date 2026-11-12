# RESULTS

**Short version:** In this pilot the rule **failed**. Among 93 US-listed oil and gas
companies from 2013 to 2019, firms that showed the warning signal went bankrupt *less*
often than firms that didn't: 30% vs 53%. The difference is not statistically reliable
(p = 0.10), and the sample is small. The main reason the rule failed is instructive: in
2013–2015 almost every producer spent more than its operating cash flow. So when banks
tightened in 2015, the "signal" lit up for nearly everyone and couldn't tell the firms
that would fail from the ones that would survive.

This is a small pilot, not proof. Every number below comes from
`data/clean/stage2_results_all_variants.csv` and `data/clean/stage2_labels_all_variants.csv`.
Each firm's label traces to SEC filings by accession number.

---

## 1. The headline test (pre-registered settings)

Version B (corrected data handling, see CHANGELOG v1.1). Bust = bankruptcy (8-K
Item 1.03). Lenders step back = Fed survey `DRTSCILM` > 0. Values as first reported.
Firms that stopped filing count as "no bust."

|                    | Bankrupt 2013–2019 | Not bankrupt |
|--------------------|-------------------:|-------------:|
| **Signal**         | 22 (TP)            | 52 (FP)      |
| **No signal**      | 10 (FN)            | 9 (TN)       |

- **n = 93 firms.** 32 went bankrupt (34%).
- **Bust rate with the signal: 22 / 74 = 30%.**
- **Base rate (bust rate with no signal): 10 / 19 = 53%.**
- Difference: −23 percentage points. Fisher's exact test, two-sided: p = 0.10.
- **False positives: 52.** Every one is named in the labels file. They include the
  largest producers in the sample (e.g. EOG, Pioneer, Devon, Occidental).
- **Strict reading (rule as a law): falsified.** There are 52 survivors of the signal
  and 10 bankruptcies without it.
- **Probabilistic reading: not supported.** The signal did not raise the bust rate
  above the base rate.

Version A (the method exactly as pre-registered) gives almost the same answer: 23/75 =
31% vs 11/20 = 55%, p = 0.065, not supported.

![Bust rates](figures/stage2_bust_rates.png)

## 2. Why it failed: the signal was almost universal

- **The shortfall was the norm, not the warning.** From 2013Q1 to 2015Q2, 87% of
  measurable firm-quarters had capex above operating cash flow (n = 856). **91 of 93
  firms** had at least one such quarter. Outspending cash flow and funding the gap with
  debt and equity was how the shale boom worked, for winners and losers alike.
- **The lender proxy flips for everyone at once.** `DRTSCILM` is one economy-wide
  number. It turned positive in 2015Q3, and **62 of the 74 signals first fired in that
  same quarter.** At the firm level, "signal" ends up mostly meaning "was still
  outspending cash flow in mid-2015."
- **Who ended up with "no signal"** (19 firms) is also telling:
  - 9 went bankrupt early or had already cut spending below cash flow by the time banks
    tightened (see the misses below).
  - 7 of the 9 true negatives stopped filing (most were acquired) before mid-2015, so
    they never had a chance to show a signal.
  - So the comparison group is shaped by timing, not by the firms' finances.

![Every firm, quarter by quarter](figures/stage2_firm_timeline.png)

## 3. The misses (false negatives), with reasons

| Reason | Firms |
|---|---|
| Shortfall happened, but not while lenders were stepping back | 9 |
| No shortfall: cash flow covered spending before the bust | 1 (Jones Energy, 2019) |

Several misses went bankrupt **before or just as** the bank survey turned positive:
Black Elk 2014Q3, Endeavour 2014Q4, Quicksilver 2015Q1, Sabine 2015Q3. A
quarterly economy-wide survey can't see the energy-specific credit squeeze that came
first. Others had already cut capex below cash flow by the time banks tightened:
Breitburn, Linn Energy (CIK 1326428, now listed as Pressburg LLC), Triangle and
Vanguard Natural Resources (now Grizzly Energy) all went bankrupt in 2016–17. Former names
are from EDGAR's own records. That pattern fits a story where **debt already taken on** matters
more than the current spending gap. This project does not measure debt.

## 4. Robustness: all 32 pre-specified variants

Full table: `data/clean/stage2_results_all_variants.csv`. In no variant does the
signal raise the bankruptcy rate (B1) with p < 0.05.

| Variation | Bust rate with signal vs base rate | Reading |
|---|---|---|
| Headline (B, B1, DRTSCILM, first, exits kept) | 30% vs 53%, p = 0.10 | not supported |
| Version A, as pre-registered | 31% vs 55%, p = 0.065 | not supported |
| Latest-filed values instead of first-reported | identical to headline | not supported |
| Side-check lender proxy (BAA10Y) | 31% vs 47%, p = 0.19 | not supported |
| Firms that stopped filing dropped (n = 74) | 35% vs 83%, p = 0.003 | not supported; the signal goes the *wrong* way |
| Bust = bankruptcy **or** a 50% capex cut (B2) | 87% vs 92% | not supported: nearly everyone "busts" |
| B2 with BAA10Y | 91% vs 81%, p = 0.37 | mixed (higher, not significant) |

The B2 rows confirm the concern written into RULE.md before any data was pulled: in
2015–16 nearly every producer cut capex by half, so "bust = 50% capex cut" can't
separate anything.

## 5. What this does and does not show

**It shows:**
- At the **firm** level, in this one industry and episode, "capex above cash flow while
  banks tighten" did not separate the producers that went bankrupt from the ones that
  survived.
- The rule's two conditions were close to universal in the 2015–16 oil bust. A rule that
  fires for almost everyone carries little information about *which* firm fails, even if
  it describes the episode as a whole.

**It does not show:**
- That the rule is wrong about **booms as a whole.** At the industry level, this episode
  matches the rule's story (an industry-wide spending gap, then lenders pulled back, then
  a third of firms went bankrupt). But that is **one** boom, one observation. It is not
  a test.
- Anything causal. The oil price (WTI) fell 75.7%, from $107.95 on 2014-06-20 to
  $26.19 on 2016-02-11 (FRED `DCOILWTICO`, US EIA data). That cut cash flow (creating
  shortfalls) and caused bankruptcies at the same time, and this design can't separate
  the two.
- That the opposite is true. The "wrong-way" result (signaled firms busted less) is
  driven by timing and composition (early busts, early takeovers), not by evidence that
  outspending is safe.

**Known blind spots and caveats:**
- **Window cutoff.** Six of the 52 false positives filed an Item 1.03 8-K in **2020**,
  outside the pre-registered window, during a different shock (COVID): Chesapeake (now
  Expand Energy), Whiting, Oasis (now Chord), Denbury, Unit and Gulfport. California
  Resources (a true negative) did too. They count as survivors here because the window
  was fixed in advance. Source: `data/clean/stage2_post_window_bankruptcies_2020_2021.csv`.
- **Bankruptcy measurement.** B1 only sees bankruptcies reported in an 8-K under the
  firm's own SEC identity. A firm that deregistered first is invisible. Example: Samson
  Resources stopped filing in August 2015 with no Item 1.03 8-K. I believe it went
  bankrupt soon after but have **not** verified that from a primary source. Defaults
  handled outside court (distressed exchanges) are also missed.
- **Universe.** SIC 1311 includes a few non-producers: pipeline partnerships, a refiner,
  an oilfield-services firm. They were kept because removing them would take judgment.
- **Small sample.** With 19 firms in the "no signal" row, one or two relabeled firms move
  the base rate by 5–10 points.

## 6. Stage 1 (descriptive only, no prediction)

As of 2026Q3, two of the five large tech spenders show a shortfall: **Oracle** (capex
1.61× operating cash flow) and **Amazon** (1.28×). Alphabet (0.89×), Meta (0.78×) and
Microsoft (0.69×) do not. Banks were net tightening in 2026Q3 (DRTSCILM = +1.7). Stage 2
suggests why this should **not** be read as a forecast: in the one boom tested, the same
pair of conditions also fit the firms that survived. Amazon met both conditions in
2022–23. Its trailing capex then fell 20% (from $66.0B in 2022Q3 to $52.7B in 2023Q4),
with no bust.

---

## Three sentences for a resume or cover letter

1. Designed and pre-registered a reproducible Python test of a boom-bust rule
   ("building booms bust when capex outruns operating cash flow and lenders pull back"),
   applied to all 93 qualifying SEC-registered oil and gas companies from 2013 to 2019
   using SEC EDGAR XBRL filings and Federal Reserve bank-lending survey data.
2. The rule failed: firms that triggered the signal went bankrupt *less* often than
   firms that didn't (30% vs 53%, n = 93, p = 0.10). Nearly every producer was already
   outspending its cash flow when banks tightened in 2015, so the signal couldn't
   separate failures from survivors.
3. Logged every data correction before looking at outcomes, including an XBRL
   year-to-date tagging artifact that produced impossible capex values, and reported all
   32 robustness variants and their limits: one industry, one episode, and a bankruptcy
   measure that misses firms that deregistered first.
