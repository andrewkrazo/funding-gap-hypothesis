# LEARN.md: the methods and traps, in plain language

Written so you can explain every step in an interview. Each section gives the idea, the
example from this project, and a short way to say it.

---

## 1. Pre-registration: write the test down before you look

**Idea.** Fix the definitions, thresholds, sample and pass/fail criteria *before* seeing
data, then publish them with a timestamp. If you decide afterward, you can (even
without meaning to) choose whichever definitions make the result look good.

**Here.** `RULE.md` was committed and pushed to GitHub (commit `7024a90`) before any data
was downloaded. Every later change is in `CHANGELOG.md` with a reason. The Stage 2
data-handling fixes were committed (`f2826e8`) before any bankruptcy data was downloaded.

**The honest limit.** Pre-registration stops you tuning to *this dataset*. It can't
erase what you already knew: everyone knows oil crashed in 2015. That's why the
thresholds are natural lines (`> 0`, capex > cash flow, half) instead of tuned numbers.

> "I wrote the rule and every threshold down and pushed it publicly before downloading
> anything, so I couldn't move the goalposts after seeing results."

## 2. The "garden of forking paths"

**Idea.** Every analysis has many small choices: which tag, which lender measure, which
date window. Try enough combinations and *something* will look significant by chance.

**Here.** Instead of picking one combination, the project reports **all 32**
pre-specified variants (`data/clean/stage2_results_all_variants.csv`). The answer is
the same across them, which is more convincing than any single run.

## 3. Year-to-date (YTD) figures: the 10-Q trap

**Idea.** In a 10-Q, the cash-flow statement is *cumulative from the start of the fiscal
year*. The Q2 10-Q shows six months, not the second quarter.

**Fix.** Subtract: Q2 = six months − three months; Q4 = full year (10-K) − nine months.
Only subtract figures with the same start date (the same fiscal year).

**Example.** Microsoft's fiscal year starts July 1, so its "Q2" ends December 31.
Oracle's year ends May 31. Each period is mapped to the calendar quarter containing its
end date. `tests/test_quarterly.py` checks all of this with small hand-made numbers.

## 4. The harder trap: tags that change between filings

**Idea.** XBRL is the machine-readable tagging behind SEC filings. Companies sometimes
tag capex one way in their 10-Qs and another way in their 10-K. Subtracting across those
filings then mixes apples and oranges.

**Here.** Chesapeake showed **−$2.9B** of capex for 2012Q3. That's impossible; cash
spending can't be negative.

**Fix (CHANGELOG v1.1).** Use the standard trailing-twelve-month identity:

> TTM = last full year (10-K) + this year-to-date − same period last year

Every 10-Q shows this year and last year side by side, so the last two numbers always
share the same tags. A unit test proves this gives exactly the same answer as the
quarter-sum method when tagging is consistent. The pre-registered method is still
reported as "Version A," and the yes/no answers agree for the median firm in every
quarter.

> "Cash-flow numbers in 10-Qs are year-to-date, so you have to difference them. And when
> firms re-tag lines between their 10-Q and 10-K, even differencing breaks, so I used
> the LTM identity, where the pieces come from a single filing."

## 5. Restatements: "as first reported" vs "latest"

**Idea.** Companies sometimes revise past numbers. The *first-reported* value is what
lenders and investors actually saw at the time. The *latest* value is the corrected one.

**Here.** Both were run. In the headline test they give identical labels, so revisions
don't drive anything.

## 6. Base rate

**Idea.** Before asking "did the signal predict busts?", ask "how often did busts happen
anyway?" A signal is only useful if busts are **more** common when it fires than when
it doesn't.

**Here.** 34% of the 93 firms went bankrupt. Firms *without* the signal went bankrupt
53% of the time (the base rate); firms *with* it, 30%. The signal did worse than the
base rate.

> "A 30% hit rate sounds informative until you notice the no-signal group was at 53%."

## 7. The confusion table: TP, FP, FN, TN

|                | Busted              | Didn't bust          |
|----------------|---------------------|----------------------|
| Signal         | True positive (TP)  | False positive (FP)  |
| No signal      | False negative (FN) | True negative (TN)   |

- **False positive** = a false alarm. Here: 52 firms showed the signal and survived
  through 2019.
- **False negative** = a miss. Here: 10 firms went bankrupt without the signal first.
- A rule can look great if you only show the TPs ("22 bankrupt firms all flashed the
  signal!"). That's why the table must be shown whole.

## 8. Fisher's exact test and p-values with small samples

**Idea.** A p-value asks: if the signal had *no* relationship to busts, how surprising
would a difference this big be? Fisher's exact test computes that exactly for a 2×2
table, which is right when counts are small.

**Here.** p = 0.10 for the headline. Not small enough to rule out chance, and the
difference goes the *wrong* direction anyway. With only 19 firms in the "no signal" row,
moving one or two firms shifts the base rate by 5–10 points.

> "p-values tell you about noise, not importance. With a sample this small, I'd treat
> any single number as a rough indication."

## 9. Survivorship bias

**Idea.** If you only study companies that exist today, you've silently dropped the ones
that died, which are exactly the cases a bust rule is about.

**Fix here.** The sample comes from the SEC's year-end-2013 "frames" snapshot, which
lists every company that reported assets for that date, **including** ones that later
went bankrupt or were acquired. Firms were selected by a mechanical rule (SIC code 1311,
assets ≥ $500M), never by name.

## 10. Selection on the outcome / hindsight

**Idea.** Hand-picking "famous blow-ups" guarantees the rule looks good. You must also
include the boring survivors and the booms that ended well.

**Here.** The mechanical rule picked 93 testable firms. 61 didn't go bankrupt, and they
are the reason the rule failed.

## 11. A signal that fires for everyone

**Idea.** A warning light that's always on carries no information. Rules that describe a
whole episode well can still be useless at telling *which* firm will fail.

**Here.** 91 of 93 producers outspent cash flow in 2013–15, which was the shale business
model. The bank survey is one economy-wide number that turned positive in 2015Q3, and 62
of 74 signals first fired in that one quarter.

> "The conditions were true of almost the whole industry, so they couldn't separate
> winners from losers. That's a design lesson: you need a measure that varies across
> firms, like each firm's own debt or its banks' decisions."

## 12. Confounding

**Idea.** A third factor can cause both the "cause" and the "effect."

**Here.** The oil price fell 75.7% (WTI, June 2014 to February 2016, FRED
`DCOILWTICO`). That crushed cash flow (creating shortfalls) *and* caused bankruptcies.
This design can't separate "shortfall plus lender pullback caused the bust" from "the
oil crash caused everything."

## 13. Censoring and windows

**Idea.** Any fixed follow-up window cuts stories off mid-way.

**Here.** The window ended in 2019, as pre-registered. Six "survivors" filed for
bankruptcy in 2020 (COVID). They stay survivors in the test because the window was fixed
in advance, but they are reported (`data/clean/stage2_post_window_bankruptcies_2020_2021.csv`).
Firms acquired before mid-2015 couldn't show a signal at all. That's why most of the
"no signal, no bust" group are early takeovers.

## 14. Measurement validity: does the measure capture the thing?

**Idea.** "Bankruptcy" here means "an 8-K under Item 1.03 filed by the firm itself."
That's clean and traceable, but it misses firms that deregistered from the SEC before
filing, and defaults settled outside court.

**Example.** Samson Resources stopped filing in August 2015 with no Item 1.03 8-K.

## 15. Firm-level vs boom-level (an ecological mismatch)

**Idea.** The rule talks about *booms* (whole industries). The test counts *firms*. At the
industry level this episode fits the rule's story, but one boom is one observation, not a
test. Testing booms properly would need many booms.

## 16. Data licensing

FRED hosts some series owned by third parties (ICE BofA, Moody's) that may not be
redistributed. This repository publishes only the Fed's own survey data and the yes/no
flag derived from the Moody's spread; the raw values stay local. A mistaken early commit
was scrubbed from the git history.

## 17. Why this counts as a good result even though the rule failed

The point was to test the rule, not to confirm it. A clean "no" with a clear reason (the
conditions were near-universal) is more useful than a cherry-picked "yes." It also points
to the next test: a firm-level lending measure, and the debt firms had already taken on.
