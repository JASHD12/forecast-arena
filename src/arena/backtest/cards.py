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


MARKETS_CARD = """# Model card: `ml` for markets (markets-ewma-t5-r1)

**What it predicts.** For EUR/USD and EUR/JPY ECB reference rates: the probability that the
absolute log change from today's fixing to the next one exceeds the question's threshold,
from an EWMA (lambda 0.94) volatility estimate of per-weekday log returns and a Student t
distribution with 5 degrees of freedom, scaled by the weekdays between the two fixings.

**Direction.** The `up` template is answered with 0.5. A direction model would only be used
if a backtest showed skill with an interval excluding zero; none was built, so the markets
domain stays a clean null test of hypothesis H3.

**Inputs.** Only the fixings published before the batch day's fixing (as-of context).

**Known limits.** No fitted parameters; lambda and the degrees of freedom are textbook
choices fixed before any live resolution, not tuned on the record.
"""


def markets_card(report_md: str, run_id: str) -> str:
    """Model card text with the generated backtest report appended."""
    return MARKETS_CARD + f"\n## Backtest (run `{run_id}`)\n\n" + report_md.split("\n", 2)[2]


ATTENTION_CARD = """# Model card: `ml` for attention (attention-hgb, revision 1)

**What it predicts.** Whether a Wikipedia article reaches at least K views on day D (R+3),
with a gradient-boosted classifier (scikit-learn `HistGradientBoostingClassifier`) and a
logistic (Platt) calibration map fitted on out-of-fold predictions.

**Inputs.** The article's views and rank on the last 7 published days from the daily top
lists (where it is absent, the list's lowest count bounds it), K relative to the views on
R, the project and the weekday of D. The same features are built in training and live.

**Training data.** Top lists only: for every eligible article ranked 5-200 on a reference
day, the label is read from the top list three days later; rows the lists cannot decide
are dropped. No per-article series are needed for training.

**Known limits.** News-driven attention depends on events the model cannot see; the agent
forecaster with news search is the comparison this domain exists for (hypothesis H2).
"""


def attention_card(report_md: str, run_id: str) -> str:
    """Model card text with the generated backtest report appended."""
    return ATTENTION_CARD + f"\n## Backtest (run `{run_id}`)\n\n" + report_md.split("\n", 2)[2]


POWER_LGBM_CARD = """# Model card: power LightGBM challenger (power-lgbq-r1)

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
"""


def power_lgbm_card(report_md: str, run_id: str) -> str:
    """Challenger card with the generated head-to-head backtest report appended."""
    return POWER_LGBM_CARD + f"\n## Backtest (run `{run_id}`)\n\n" + report_md.split("\n", 2)[2]


POWER_MLP_CARD = """# Model card: power PyTorch challenger (power-mlpq-r1)

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
"""


def power_mlp_card(report_md: str, run_id: str) -> str:
    """Challenger card with the generated head-to-head backtest report appended."""
    return POWER_MLP_CARD + f"\n## Backtest (run `{run_id}`)\n\n" + report_md.split("\n", 2)[2]


POWER_TS_CARD = """# Model card: power time-series benchmarks (ts_ets, ts_sarimax, ts_chronos)

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
"""


def power_ts_card(report_md: str, run_id: str) -> str:
    """Benchmark card with the generated backtest report appended."""
    return POWER_TS_CARD + f"\n## Backtest (run `{run_id}`)\n\n" + report_md.split("\n", 2)[2]
