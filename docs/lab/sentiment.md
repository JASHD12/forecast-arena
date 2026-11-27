# News tone (GDELT) as a crypto forecaster: sentiment-gdelt-r1 against ml

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-sentiment.json`, created 2026-11-27T21:41:02.715881+00:00.

Why companies use it: Sentiment from news and social media is a common feature in forecasting products; this is the pre-registered test of whether it adds anything for crypto. (gdelt-doc-api)

| Variant | Questions | Brier |
|---|---|---|
| questions / bigmove | 1220 | - |
| sentiment / bigmove | 607 | 0.2406 |
| ml / bigmove | 607 | 0.2375 |
| base_rate / bigmove | 607 | 0.2572 |
| always_0.5 / bigmove | 607 | 0.25 |
| questions / up | 565 | - |
| sentiment / up | 215 | 0.2584 |
| ml / up | 215 | 0.25 |
| base_rate / up | 215 | 0.2517 |
| always_0.5 / up | 215 | 0.25 |

- sentiment minus ml: Brier difference +0.0031, 95% interval [-0.0005, +0.0068] over 607 questions (interval includes zero).
- sentiment minus base_rate: Brier difference -0.0165, 95% interval [-0.0286, -0.0053] over 607 questions (interval excludes zero).
- sentiment minus always_0.5: Brier difference -0.0094, 95% interval [-0.0195, +0.0011] over 607 questions (interval includes zero).
- sentiment minus base_rate: Brier difference +0.0067, 95% interval [-0.0035, +0.0176] over 215 questions (interval includes zero).
- sentiment minus always_0.5: Brier difference +0.0084, 95% interval [-0.0100, +0.0270] over 215 questions (interval includes zero).

- Backtest (I4): never part of a live score. Walk-forward from 2026-03-12, refit every 7 days, no outcome used before it was known. Paired day-block bootstrap intervals.
- bigmove: 607 scored questions, fewer than 800: inconclusive
- up: 215 scored questions, fewer than 800: inconclusive

## What this does and does not show

- CoinGecko's demo history is 365 days, so there is no held-out year (stated in the pre-registration); the test period is the last part of one year.
- GDELT counts per day are small for these queries (single or double digits for most days), so the tone is a noisy feature.
- 41 of 50 GDELT history chunks were recorded; days in missing chunks have no features and are not scored for any arm.
- Many test questions have no usable GDELT numbers (a day without matching articles has no tone, or its chunk was not recorded): see the 'questions' rows. Those are not scored for any arm, so the comparison is on the days with news only.
- No claim about prediction of price direction beyond this period, and no advice.

Paid-call cost: US$0.00.
