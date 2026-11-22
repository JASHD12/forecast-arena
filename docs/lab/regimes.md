# Price-regime clustering (k-means) as a feature for the next day's mean price

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-regimes.json`, created 2026-11-22T10:27:03Z.

Why companies use it: Unsupervised structure (clusters of daily shapes) is a standard source of features and of operational monitoring in energy forecasting.

| Variant | Questions |
|---|---|
| without_regime | 365 |
| with_regime | 365 |

- with_regime minus without_regime: Brier difference -0.0218, 95% interval [-0.1611, +0.1073] over 365 questions (interval includes zero).

- k = 2 chosen by silhouette on 2019-01-01 to 2025-10-31 (silhouette by k: {2: 0.3079, 3: 0.2299, 4: 0.2313, 5: 0.2294, 6: 0.1988}); share of training days per regime in percent: [np.float64(48.8), np.float64(51.2)].
- Pinball loss averaged over the 10%, 50% and 90% quantiles of the next day's mean price, test year 2025-11-01 to 2026-10-31; the regime is that of the last known day.

## What this does and does not show

- One market, one year of test days; the interval is a day-block bootstrap.
- Backtest-only: nothing changes in the live `ml` forecaster.

Paid-call cost: US$0.00.
