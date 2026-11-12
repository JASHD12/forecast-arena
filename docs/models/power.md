# Model card: `ml` for power (power-gbq, revision 1)

**What it predicts.** For tomorrow's German/Luxembourg day-ahead prices, the quantiles
0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98 of each daily statistic (mean, max, min, spread, evening), with
one gradient-boosted quantile regressor per statistic and quantile (scikit-learn
`HistGradientBoostingRegressor`, pinball loss). P(statistic > T) is read from the linearly
interpolated predicted CDF (tails halved beyond the outer quantiles) and calibrated with a
logistic (Platt) map fitted on out-of-fold predictions of earlier real questions.

**Inputs.** Only what the as-of context gives the forecaster: the last 28 known days of
daily statistics, plus the calendar of the target day (weekday, season, German national
holidays). No load, generation, weather or official forecast data yet.

**Validation.** Expanding-window time-series validation with a 7-day gap, never shuffled;
the backtest below replays the same question, context and resolver code as production.

**Known limits.** Prices react to weather and plant availability, which the model does not
see; it can only learn calendar and persistence patterns. The model is shipped whether or
not it beats the baselines; the backtest says which.

## Backtest (run `power-2025-11-01-2026-10-31-20261112T1356`)

**BACKTEST** (not part of the live record).

Batches 2025-11-01 to 2026-10-31 (365 batch days).
Observed YES rate on scored questions: 0.483 (a constant forecast of that rate would score Brier 0.2497).

| Forecaster | n | Brier | 95% interval | Log score |
|---|---|---|---|---|
| base_rate | 2190 | 0.2466 | [0.2424, 0.2510] | 0.6860 |
| persistence | 2190 | 0.2205 | [0.2107, 0.2302] | 0.6327 |
| ml | 2190 | 0.1930 | [0.1818, 0.2043] | 0.5683 |

Paired Brier differences (negative = first is better), day-block bootstrap, 2000 replicates, fixed seed:

| Comparison | Difference | 95% interval | Supported? |
|---|---|---|---|
| ml - base_rate | -0.0536 | [-0.0655, -0.0414] | yes |
| ml - persistence | -0.0275 | [-0.0378, -0.0162] | yes |
| persistence - base_rate | -0.0261 | [-0.0357, -0.0159] | yes |

Notes:

- Features: calendar (weekday, season, German national holidays) and the last 28 days of daily price statistics from the as-of context only.
- Not used: load/generation actuals, weather forecasts and official day-ahead forecasts (no as-of history of forecasts is available; adding them would make a backtest 'optimistic').
- Models are retrained on an expanding window every `retrain_days`, each time with targets up to the day before the batch; calibration uses out-of-fold predictions.
- Baselines learn only from outcomes known by each morning of the walk-forward (after a warm-up period whose forecasts are not scored).
