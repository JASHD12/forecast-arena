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

## Weekly evaluation

Window 2026-10-16 to 2026-11-12, 168 questions; candidate Brier 0.13950686466104695, current None.
