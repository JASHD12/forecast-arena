# 02 - Power market questions

How the electricity-price questions are generated from public data, resolved
automatically, and kept fair for every forecaster.
Code: `src/arena/sources/smard.py`, `src/arena/domains/power.py`,
`src/arena/domains/power_history.py`, `src/arena/domains/base.py` (as-of store).

## How it works

1. **The data.** SMARD, the Bundesnetzagentur's market data platform, publishes the
   hourly day-ahead price for the Germany/Luxembourg bidding zone (filter 4169, region DE,
   hourly resolution; the market trades 15-minute products since October 2025 and the
   hourly series averages them). Data come as weekly JSON chunks with epoch-millisecond
   timestamps. Licence CC BY 4.0, credited as "Bundesnetzagentur | SMARD.de".
2. **The timeline.** Batch day B. Questions are about delivery day D = B + 1 in
   Europe/Berlin time. Forecasts lock at B 09:30 UTC. The day-ahead auction for D clears
   around midday on B and SMARD publishes it in the afternoon (the code assumes it is
   known no earlier than 14:00 Berlin, a conservative stamp). Resolution starts at
   B 12:30 UTC; if any hour of D is still missing 30 hours later, the question is void.
3. **Clock changes.** A Berlin day has 23, 24 or 25 hours. The code builds the hour list
   from the time zone (`berlin_day_hours`) instead of assuming 24, and tests cover both
   switch days.
4. **Templates.** Six yes/no templates per day:

   | Template | Question | Threshold |
   |---|---|---|
   | `mean_gt` | daily mean price above T? | median of daily means, 28 days |
   | `max_gt` | highest hourly price above T? | 60th percentile of daily maxima, 28 days |
   | `min_lt` | lowest hourly price below T? | 0 EUR/MWh if negative-price days were 10-90% of the last 60 days, else their 40th percentile |
   | `spread_gt` | max minus min above T? | median of daily spreads, 28 days |
   | `evening_gt` | mean of 17:00-20:00 Berlin above T? | median of that block, 28 days |
   | `up_vs_today` | mean on D above the mean on B? | the mean on B itself |

   Thresholds are rounded to whole EUR/MWh; statistics are rounded half-up to two
   decimals (SMARD's precision) and compared strictly, so ties are NO.
5. **Degeneracy rule.** A template is skipped (and the skip logged) when its YES rate over
   the trailing window is below 10% or above 90%: such a question tells us little and
   rewards always saying the same thing.
6. **The as-of gateway.** Every observation is stored with the time it became available
   (`AsOfStore`). A forecaster's context is built only from observations available at
   forecast time. At the lock, the prices for B are known (published on B-1) but the
   prices for D are not. A test checks that the threshold window never contains the
   target day or anything later (`test_window_never_contains_target_or_future`).
7. **Resolution.** After resolve_after, the resolve job fetches D's hours, computes the
   statistic exactly as the rule text says, and appends a resolution with the evidence
   (source URL, values used). A revision found within 7 days becomes a `source_revised`
   void; scores keep the first resolution.
8. **Question text.** Every question carries the full rule in plain words, the threshold
   and how it was derived, so it can be resolved by hand by anyone with the SMARD data.

## Why it was built this way

- **Thresholds from the recent past.** A median threshold makes the base rate near 50%,
  so questions are informative and a constant forecaster cannot look good. Rules are fixed
  in advance, so nobody picks thresholds after seeing a forecast.
- **Day-ahead prices** are published once, at a known time, by an official body, under an
  open licence, with years of history. That makes them ideal for automatic resolution and
  for backtesting the classical model (one year, 2,190 questions).
- **Strict comparisons and explicit rounding** remove ambiguity; ambiguity in a rule is
  where disputes and quiet tuning come from.
- **Conservative availability stamps** may waste a little information but can never leak
  future data, which matters more (integrity rule I3).

## What was rejected

- Intraday or 15-minute questions (more rules, noisier data, harder to explain).
- Exact-value or range questions (the benchmark scores yes/no probabilities only).
- Thresholds to 0.1 EUR/MWh (false precision) and nearest-rank percentiles (jumpier).
- Scraping exchange (EPEX) pages: SMARD gives the same prices under an open licence.

## Honest limits

- Six questions per day from one market are strongly correlated (one windy day moves all
  of them), which is why statistics resample days, not questions.
- The `up_vs_today` question leans on the most recent known day, which favours simple
  persistence-style models; that is a property of the question, reported as such.
- If SMARD changes its data format or a filter id, questions are skipped and the health
  check opens an incident; nothing is guessed.

## Ten interview questions

1. **Why electricity prices?**
   An official source publishes them once a day at a known time under an open licence,
   with years of history. The answer arrives a few hours after the lock, so the feedback
   loop is one day, and there are real drivers (wind, solar, demand) to reason about.
2. **How do you prevent look-ahead bias?**
   All forecaster data go through an as-of store that indexes each value by when it was
   published. The prices for D are stamped as available at 14:00 Berlin on B, after the
   09:30 UTC lock, so no forecaster can see them. Tests check that windows never reach
   the target day.
3. **How are thresholds chosen?**
   By fixed rules from the trailing window, for example the median of the last 28 daily
   means, rounded to a whole EUR/MWh. That puts the base rate near 50% and the rule is
   written into each question.
4. **What happens on daylight-saving days?**
   The day has 23 or 25 hours. Hours come from the time zone, not a fixed 24, so means and
   the evening block are still correct; tests cover both dates.
5. **What if SMARD is late or missing data?**
   The question waits up to 30 hours after resolve_after, then becomes void with reason
   `source_missing`. Voids are not scored and are listed on the Status page.
6. **What if SMARD revises a price later?**
   The resolve job rechecks for 7 days. A change is recorded as a new `source_revised`
   void; the first resolution stays in the scores, so an outcome cannot be re-picked.
7. **Why skip "degenerate" templates?**
   If a template was YES on 95% of recent days, always saying 0.95 looks great and teaches
   nothing. Skipping outside 10-90% keeps questions informative, and each skip is logged.
8. **Are the six questions independent?**
   No. They share the same day's weather and demand. That is why the bootstrap resamples
   whole days and why the power analysis on the Findings page uses daily differences.
9. **What does the classical model do here?**
   It predicts quantiles of each daily statistic from lagged prices and calendar
   features, then turns them into a probability of exceeding the threshold. In a one-year
   backtest it scored Brier 0.193 against 0.247 for the base rate; a LightGBM challenger
   was slightly better (0.188) and a small PyTorch network was no better than the
   champion. These are backtest numbers and never enter the live record.
10. **What would you change with more time?**
   Add the published wind and solar forecasts as features through the same as-of
   gateway, and questions on other bidding zones. Both need new template versions, so the
   old records stay comparable.
