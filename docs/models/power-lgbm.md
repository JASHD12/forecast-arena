# Model card: power LightGBM challenger (power-lgbq-r1)

**What it is.** The same probabilistic model as the power champion (`power-gbq`): 13
quantile regressors per daily price statistic, the predicted distribution read off at the
question's threshold, Platt-calibrated on out-of-fold predictions. Only the learner
differs: LightGBM (objective `quantile`) with hyperparameters tuned by Optuna (TPE, seed 0,
20 trials; two time-series folds with a 7-day gap; mean pinball loss at 0.1/0.5/0.9).

**Role.** A challenger in the weekly champion/challenger job (`arena.ops.weekly`): it
becomes the live `ml` model only if it scores at least as well as the champion on the same
recent questions. SHAP (TreeExplainer) explains it when it is promoted.

**Inputs.** Identical to the champion: calendar features and the last 28 days of daily
price statistics from the as-of context only.

**Known limits.** Same as the champion. The tuning objective (pinball loss of the daily
mean) is a proxy for the Brier score of the yes/no questions.

## Backtest (run `power-2025-11-01-2026-10-31-20261113T0815`)

**BACKTEST** (not part of the live record).

Batches 2025-11-01 to 2026-10-31 (365 batch days).
Observed YES rate on scored questions: 0.483 (a constant forecast of that rate would score Brier 0.2497).

| Forecaster | n | Brier | 95% interval | Log score |
|---|---|---|---|---|
| base_rate | 2190 | 0.2466 | [0.2424, 0.2510] | 0.6860 |
| persistence | 2190 | 0.2205 | [0.2107, 0.2302] | 0.6327 |
| ml | 2190 | 0.1930 | [0.1818, 0.2043] | 0.5683 |
| ml_lgbm | 2190 | 0.1884 | [0.1773, 0.1997] | 0.5584 |

Paired Brier differences (negative = first is better), day-block bootstrap, 2000 replicates, fixed seed:

| Comparison | Difference | 95% interval | Supported? | Diebold-Mariano |
|---|---|---|---|---|
| ml - base_rate | -0.0536 | [-0.0655, -0.0414] | yes | DM = -7.70, p = 0.000 |
| ml - persistence | -0.0275 | [-0.0378, -0.0162] | yes | DM = -5.43, p = 0.000 |
| persistence - base_rate | -0.0261 | [-0.0357, -0.0159] | yes | DM = -4.49, p = 0.000 |
| ml_lgbm - ml | -0.0045 | [-0.0069, -0.0021] | yes | DM = -4.10, p = 0.000 |
| ml_lgbm - base_rate | -0.0581 | [-0.0698, -0.0460] | yes | DM = -8.51, p = 0.000 |

Notes:

- Features: calendar (weekday, season, German national holidays) and the last 28 days of daily price statistics from the as-of context only.
- Not used: load/generation actuals, weather forecasts and official day-ahead forecasts (no as-of history of forecasts is available; adding them would make a backtest 'optimistic').
- Models are retrained on an expanding window every `retrain_days`, each time with targets up to the day before the batch; calibration uses out-of-fold predictions.
- Baselines learn only from outcomes known by each morning of the walk-forward (after a warm-up period whose forecasts are not scored).
