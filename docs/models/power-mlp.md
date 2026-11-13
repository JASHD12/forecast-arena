# Model card: power PyTorch challenger (power-mlpq-r1)

**What it is.** The power champion's probabilistic model with a neural learner: one
multi-layer perceptron (two hidden layers of 64 ReLU units) predicts all 13 quantile levels
of a daily price statistic at once, trained with the summed pinball loss (full-batch Adam,
learning rate 1e-3, weight decay 1e-4, 400 epochs, CPU, fixed seed, deterministic
algorithms). Inputs and target are standardised; predicted quantiles are sorted so they
never cross. Calibration and question logic are the champion's.

**Role.** A challenger in the weekly champion/challenger job; promoted only if it scores at
least as well as the champion on the same recent questions.

**Known limits.** A few hundred training rows per statistic are a small sample for a
neural network; gradient-boosted trees are the usual strong baseline on such tabular data.

## Backtest (run `power-2025-11-01-2026-10-31-20261113T0838`)

**BACKTEST** (not part of the live record).

Batches 2025-11-01 to 2026-10-31 (365 batch days).
Observed YES rate on scored questions: 0.483 (a constant forecast of that rate would score Brier 0.2497).

| Forecaster | n | Brier | 95% interval | Log score |
|---|---|---|---|---|
| base_rate | 2190 | 0.2466 | [0.2424, 0.2510] | 0.6860 |
| persistence | 2190 | 0.2205 | [0.2107, 0.2302] | 0.6327 |
| ml | 2190 | 0.1930 | [0.1818, 0.2043] | 0.5683 |
| ml_mlp | 2190 | 0.1927 | [0.1806, 0.2052] | 0.5678 |

Paired Brier differences (negative = first is better), day-block bootstrap, 2000 replicates, fixed seed:

| Comparison | Difference | 95% interval | Supported? | Diebold-Mariano |
|---|---|---|---|---|
| ml - base_rate | -0.0536 | [-0.0655, -0.0414] | yes | DM = -7.70, p = 0.000 |
| ml - persistence | -0.0275 | [-0.0378, -0.0162] | yes | DM = -5.43, p = 0.000 |
| persistence - base_rate | -0.0261 | [-0.0357, -0.0159] | yes | DM = -4.49, p = 0.000 |
| ml_mlp - ml | -0.0003 | [-0.0087, +0.0081] | no (interval includes zero) | DM = -0.06, p = 0.951 |
| ml_mlp - base_rate | -0.0539 | [-0.0662, -0.0413] | yes | DM = -8.55, p = 0.000 |

Notes:

- Features: calendar (weekday, season, German national holidays) and the last 28 days of daily price statistics from the as-of context only.
- Not used: load/generation actuals, weather forecasts and official day-ahead forecasts (no as-of history of forecasts is available; adding them would make a backtest 'optimistic').
- Models are retrained on an expanding window every `retrain_days`, each time with targets up to the day before the batch; calibration uses out-of-fold predictions.
- Baselines learn only from outcomes known by each morning of the walk-forward (after a warm-up period whose forecasts are not scored).
