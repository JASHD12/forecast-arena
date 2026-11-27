# News tone (GDELT) as a crypto forecaster: sentiment-gdelt-r1 against ml

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-sentiment.json`, created 2026-11-27T22:13:02.899442+00:00.

Why companies use it: Sentiment from news and social media is a common feature in forecasting products; this is the pre-registered test of whether it adds anything for crypto. (gdelt-doc-api)

| Variant | Questions | Brier |
|---|---|---|
| questions / bigmove | 1220 | - |
| sentiment / bigmove | 887 | 0.2403 |
| ml / bigmove | 887 | 0.2372 |
| base_rate / bigmove | 887 | 0.2574 |
| always_0.5 / bigmove | 887 | 0.25 |
| questions / up | 565 | - |
| sentiment / up | 302 | 0.2595 |
| ml / up | 302 | 0.25 |
| base_rate / up | 302 | 0.2528 |
| always_0.5 / up | 302 | 0.25 |

- sentiment minus ml: Brier difference +0.0032, 95% interval [-0.0003, +0.0066] over 887 questions (interval includes zero).
- sentiment minus base_rate: Brier difference -0.0170, 95% interval [-0.0280, -0.0071] over 887 questions (interval excludes zero).
- sentiment minus always_0.5: Brier difference -0.0097, 95% interval [-0.0192, -0.0005] over 887 questions (interval excludes zero).
- sentiment minus base_rate: Brier difference +0.0067, 95% interval [-0.0027, +0.0171] over 302 questions (interval includes zero).
- sentiment minus always_0.5: Brier difference +0.0095, 95% interval [-0.0014, +0.0210] over 302 questions (interval includes zero).

- Backtest (I4): never part of a live score. Walk-forward from 2026-03-12, refit every 7 days, no outcome used before it was known. Paired day-block bootstrap intervals.
- up: 302 scored questions, fewer than 800: inconclusive

## What this does and does not show

- CoinGecko's demo history is 365 days, so there is no held-out year (stated in the pre-registration); the test period is the last part of one year.
- GDELT counts per day are small for these queries (single or double digits for most days), so the tone is a noisy feature.
- 46 of 50 GDELT history chunks were recorded; days in missing chunks have no features and are not scored for any arm.
- Many test questions have no usable GDELT numbers (a day without matching articles has no tone, or its chunk was not recorded): see the 'questions' rows. Those are not scored for any arm, so the comparison is on the days with news only.
- No claim about prediction of price direction beyond this period, and no advice.

Paid-call cost: US$0.00.
