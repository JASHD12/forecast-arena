"""Model cards: fixed text about the model plus the generated backtest report."""

from __future__ import annotations

from arena.forecasters.ml_power import MODEL_FAMILY, MODEL_REVISION, QUANTILES, STATS

POWER_CARD = f"""# Model card: `ml` for power ({MODEL_FAMILY}, revision {MODEL_REVISION})

**What it predicts.** For tomorrow's German/Luxembourg day-ahead prices, the quantiles
{", ".join(str(q) for q in QUANTILES)} of each daily statistic ({", ".join(STATS)}), with
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
"""


def power_card(report_md: str, run_id: str) -> str:
    """Model card text with the generated backtest report appended."""
    return POWER_CARD + f"\n## Backtest (run `{run_id}`)\n\n" + report_md.split("\n", 2)[2]
