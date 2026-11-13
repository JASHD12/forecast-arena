# Model card: power time-series benchmarks (ts_ets, ts_sarimax, ts_chronos)

**What they are.** Three *local* benchmarks for the power champion. For each question they
look only at the as-of context (the daily statistic on the last 28 known days) and forecast
that statistic for the target day, then read P(YES) from the predictive distribution:

- `ts_ets` (power-ets-r1): exponential smoothing with additive errors and additive weekly
  seasonality (statsmodels `ETSModel`), Gaussian predictive.
- `ts_sarimax` (power-sarimax-r1): SARIMA(1,0,0)(1,0,0)[7] with a constant (statsmodels
  `SARIMAX`), Gaussian predictive.
- `ts_chronos` (power-chronos-bolt-tiny-r1): Chronos-Bolt tiny, a 9M-parameter pretrained
  time-series foundation model (Amazon, Apache-2.0), zero-shot on the same 28 values,
  CPU, weights pinned to revision `a0e552de`; its nine predicted quantiles 0.1..0.9 are
  interpolated into a CDF.

**Role.** Benchmarks in the backtest table only; not live forecasters and not candidates
for promotion. Nothing is trained on other days and nothing is calibrated afterwards.

**Known limits.** 28 values is a short context, chosen so every model sees exactly what
the live forecasters see. No calendar or holiday features, which the champion has.

## Backtest (run `power-2025-11-01-2026-10-31-20261113T0954`)

**BACKTEST** (not part of the live record).

Batches 2025-11-01 to 2026-10-31 (365 batch days).
Observed YES rate on scored questions: 0.483 (a constant forecast of that rate would score Brier 0.2497).

| Forecaster | n | Brier | 95% interval | Log score |
|---|---|---|---|---|
| base_rate | 2190 | 0.2466 | [0.2424, 0.2510] | 0.6860 |
| persistence | 2190 | 0.2205 | [0.2107, 0.2302] | 0.6327 |
| ml | 2190 | 0.1930 | [0.1818, 0.2043] | 0.5683 |
| ts_ets | 2190 | 0.2441 | [0.2263, 0.2616] | 0.7466 |
| ts_sarimax | 2190 | 0.2279 | [0.2181, 0.2377] | 0.6607 |
| ts_chronos | 2190 | 0.2142 | [0.2040, 0.2243] | 0.6227 |

Paired Brier differences (negative = first is better), day-block bootstrap, 2000 replicates, fixed seed:

| Comparison | Difference | 95% interval | Supported? | Diebold-Mariano |
|---|---|---|---|---|
| ml - base_rate | -0.0536 | [-0.0655, -0.0414] | yes | DM = -7.70, p = 0.000 |
| ml - persistence | -0.0275 | [-0.0378, -0.0162] | yes | DM = -5.43, p = 0.000 |
| persistence - base_rate | -0.0261 | [-0.0357, -0.0159] | yes | DM = -4.49, p = 0.000 |
| ts_ets - ml | +0.0511 | [+0.0355, +0.0671] | yes | DM = +5.96, p = 0.000 |
| ts_sarimax - ml | +0.0349 | [+0.0240, +0.0458] | yes | DM = +6.39, p = 0.000 |
| ts_chronos - ml | +0.0212 | [+0.0109, +0.0318] | yes | DM = +4.37, p = 0.000 |
| ts_ets - base_rate | -0.0025 | [-0.0208, +0.0154] | no (interval includes zero) | DM = -0.23, p = 0.819 |
| ts_sarimax - base_rate | -0.0187 | [-0.0287, -0.0086] | yes | DM = -2.79, p = 0.006 |
| ts_chronos - base_rate | -0.0324 | [-0.0431, -0.0215] | yes | DM = -4.66, p = 0.000 |

Notes:

- Features: calendar (weekday, season, German national holidays) and the last 28 days of daily price statistics from the as-of context only.
- Not used: load/generation actuals, weather forecasts and official day-ahead forecasts (no as-of history of forecasts is available; adding them would make a backtest 'optimistic').
- Models are retrained on an expanding window every `retrain_days`, each time with targets up to the day before the batch; calibration uses out-of-fold predictions.
- Baselines learn only from outcomes known by each morning of the walk-forward (after a warm-up period whose forecasts are not scored).
