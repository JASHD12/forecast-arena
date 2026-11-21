# Model card: power global LightGBM challenger (power-glgbq-r1)

**What it is.** One LightGBM quantile model per level (13 in total) fitted on the rows of all
five daily price statistics stacked, with the statistic as a one-hot feature and each target
standardised by its training mean and standard deviation; the pattern used in demand
forecasting (one global model over related series). Hyperparameters are the LightGBM
challenger's defaults, not tuned per statistic. Features, calibration (Platt on out-of-fold
predictions) and question logic are the champion's.

**Role.** A challenger in the weekly champion/challenger job (`glgbm` family): it becomes the
live `ml` model only if it scores at least as well as the champion on the same recent
questions. It trains five times fewer models than the per-statistic families.

**Known limits.** Sharing one model across statistics can hurt a statistic with a different
shape (spread); the standardisation only fixes the scale. Same limits as the champion.

## Backtest (run `power-2025-11-01-2026-10-31-20261121T2213`)

**BACKTEST** (not part of the live record).

Batches 2025-11-01 to 2026-10-31 (365 batch days).
Observed YES rate on scored questions: 0.483 (a constant forecast of that rate would score Brier 0.2497).

| Forecaster | n | Brier | 95% interval | Log score |
|---|---|---|---|---|
| base_rate | 2190 | 0.2466 | [0.2424, 0.2510] | 0.6860 |
| persistence | 2190 | 0.2205 | [0.2107, 0.2302] | 0.6327 |
| ml | 2190 | 0.1930 | [0.1818, 0.2043] | 0.5683 |
| ml_glgbm | 2190 | 0.2079 | [0.1974, 0.2186] | 0.6034 |

Paired Brier differences (negative = first is better), day-block bootstrap, 2000 replicates, fixed seed:

| Comparison | Difference | 95% interval | Supported? | Diebold-Mariano |
|---|---|---|---|---|
| ml - base_rate | -0.0536 | [-0.0655, -0.0414] | yes | DM = -7.70, p = 0.000 |
| ml - persistence | -0.0275 | [-0.0378, -0.0162] | yes | DM = -5.43, p = 0.000 |
| persistence - base_rate | -0.0261 | [-0.0357, -0.0159] | yes | DM = -4.49, p = 0.000 |
| ml_glgbm - ml | +0.0149 | [+0.0097, +0.0198] | yes | DM = +4.11, p = 0.000 |
| ml_glgbm - base_rate | -0.0387 | [-0.0504, -0.0270] | yes | DM = -5.14, p = 0.000 |

Notes:

- Features: calendar (weekday, season, German national holidays) and the last 28 days of daily price statistics from the as-of context only.
- Not used: load/generation actuals, weather forecasts and official day-ahead forecasts (no as-of history of forecasts is available; adding them would make a backtest 'optimistic').
- Models are retrained on an expanding window every `retrain_days`, each time with targets up to the day before the batch; calibration uses out-of-fold predictions.
- Baselines learn only from outcomes known by each morning of the walk-forward (after a warm-up period whose forecasts are not scored).
