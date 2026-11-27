# News tone (GDELT) as a crypto forecaster: sentiment-gdelt-r1 against ml

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-sentiment.json`, created 2026-11-27T22:27:41.263926+00:00.

Why companies use it: Sentiment from news and social media is a common feature in forecasting products; this is the pre-registered test of whether it adds anything for crypto. (gdelt-doc-api)

| Variant | Questions | Brier |
|---|---|---|
| questions / bigmove | 1220 | - |
| sentiment / bigmove | 1000 | 0.2412 |
| ml / bigmove | 1000 | 0.2372 |
| base_rate / bigmove | 1000 | 0.2574 |
| always_0.5 / bigmove | 1000 | 0.25 |
| questions / up | 565 | - |
| sentiment / up | 305 | 0.2592 |
| ml / up | 305 | 0.25 |
| base_rate / up | 305 | 0.2529 |
| always_0.5 / up | 305 | 0.25 |

- sentiment minus ml: Brier difference +0.0039, 95% interval [+0.0001, +0.0081] over 1000 questions (interval excludes zero).
- sentiment minus base_rate: Brier difference -0.0162, 95% interval [-0.0252, -0.0076] over 1000 questions (interval excludes zero).
- sentiment minus always_0.5: Brier difference -0.0088, 95% interval [-0.0169, -0.0008] over 1000 questions (interval excludes zero).
- sentiment minus base_rate: Brier difference +0.0063, 95% interval [-0.0031, +0.0164] over 305 questions (interval includes zero).
- sentiment minus always_0.5: Brier difference +0.0092, 95% interval [-0.0016, +0.0207] over 305 questions (interval includes zero).

- Backtest (I4): never part of a live score. Walk-forward from 2026-03-12, refit every 7 days, no outcome used before it was known. Paired day-block bootstrap intervals.
- up: 305 scored questions, fewer than 800: inconclusive

## What this does and does not show

- CoinGecko's demo history is 365 days, so there is no held-out year (stated in the pre-registration); the test period is the last part of one year.
- GDELT counts per day are small for these queries (single or double digits for most days), so the tone is a noisy feature.
- 49 of 50 GDELT history chunks were recorded; days in missing chunks have no features and are not scored for any arm.
- Many test questions have no usable GDELT numbers (a day without matching articles has no tone, or its chunk was not recorded): see the 'questions' rows. Those are not scored for any arm, so the comparison is on the days with news only.
- No claim about prediction of price direction beyond this period, and no advice.

Paid-call cost: US$0.00.
