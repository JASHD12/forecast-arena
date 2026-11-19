# 04 - The classical models: training without leakage, calibration, promotion

How the `ml` forecaster works for each domain, how its models are trained so that they never
see the future, how raw model output becomes an honest probability, and how a new model
replaces the current one. Code: `src/arena/forecasters/ml.py` (the live forecaster),
`ml_power.py`, `ml_attention.py`, `ml_weather.py`, `ml_markets.py` (one model per domain),
`ml_power_lgbm.py` and `ml_power_torch.py` (challengers), `registry.py` (versioned
artifacts), `src/arena/ops/weekly.py` (retrain, compare, promote), `src/arena/backtest/`.

## How it works

1. **One forecaster id, one model family per domain.** The live forecaster is just `ml`.
   Underneath, `MLForecaster` holds a model per domain:
   - **power:** gradient-boosted *quantile* regressors (scikit-learn
     `HistGradientBoostingRegressor`, pinball loss) for each daily statistic (mean, max,
     min, spread, evening block). The probability of "statistic above T" is read from the
     interpolated predicted distribution.
   - **attention:** a boosted classifier on the article's last 7 days of views and ranks, the
     question's K relative to recent views, the language project and the weekday.
   - **weather:** transparent rules on the DWD MOSMIX forecast (a normal distribution around
     the forecast maximum with a fixed 2.0 °C spread; a step function for rain). The rules
     were fixed before any live question resolved, because there is no as-of history of
     forecasts yet to train on.
   - **markets:** EWMA volatility (RiskMetrics lambda 0.94) with a Student-t tail; the
     direction question is always 0.5.
2. **Features are the same in training and live.** The model only sees the context the as-of
   gateway builds: lagged daily price statistics, the calendar of the target day (weekday,
   season, German national holidays), top-list trajectories, fixings known before the lock.
   There is one code path for building them, used by the backtest, the weekly training and
   the morning job.
3. **No leakage by construction.** Training targets stop before the batch day; validation is an
   expanding window with a gap (7 days for power), never shuffled, because neighbouring days
   are correlated and shuffling would let tomorrow's data train a model that predicts
   today. The backtest replays the real question, context and resolver code day by day
   (walk-forward), so it cannot use anything a live run could not.
4. **Calibration.** A raw model score is not a probability. For power and attention, a logistic
   (Platt) map is fitted on *out-of-fold* predictions of earlier questions and applied to the
   model's output. Reliability diagrams and the expected calibration error on the site check
   whether "70%" means about 70%.
5. **Versioned, hashed artifacts.** Only promoted models are stored, as
   `models/<domain>/<version>/model.joblib.xz` plus metadata and a model card, on the `ledger`
   branch. A promotion is one file naming the version. The forecast records the version and
   the artifact's SHA-256, so every live probability can be traced to the exact file.
6. **Weekly champion and challenger.** Every Sunday, `weekly.py` trains candidates (the champion
   recipe, a tuned LightGBM, a small PyTorch network for power), scores each on the last 28
   days of real questions next to the current model, and promotes a candidate only if its
   Brier score is not worse. The first candidate for a domain is promoted. The run is logged
   with MLflow and a JSON summary is written to the public ledger.
7. **Failures are visible, never replaced.** If the artifact is missing or fails to load, `ml`
   writes a skip with a reason (`model_missing`, `error`); an out-of-range or NaN
   probability is also a skip. There is no fallback to 0.5.

## Why it was built this way

- **Quantiles, then a probability.** The question is "above T?" for many different T, so
  predicting the distribution of the statistic once serves every threshold.
- **Boosted trees over deep nets for small tabular data.** 365 days of a few features suit
  gradient boosting; the PyTorch challenger exists to test that claim, and it lost.
- **Promotion by rule, not by eye.** A written, symmetric rule (not worse than the current
  model on the same recent questions) stops anyone, including the owner, from swapping in a
  model because of how one live question resolved (integrity rule I8).
- **Hashes and versions in every forecast** make the record auditable and let the site show a
  model timeline.

## What was rejected

- Random train/test splits and shuffled cross-validation (leakage through autocorrelation).
- Tuning anything on the live record: improvements go through new versions and backtests.
- Training the weather model before 60 days of forecast snapshots exist: a model trained on
  today's copy of past forecasts would be optimistic.
- A larger model zoo in production: the extra families run as challengers in the weekly job
  and in the backtest, not daily.

## Honest limits

- **Backtest is not live.** The one-year electricity backtest shows the champion clearly
  better than the base rate and persistence, and the LightGBM challenger slightly better again.
  The PyTorch network is not better than the champion (its interval includes zero). These are
  replays; the live comparison is still "too early to tell".
- **The model does not see the physical drivers.** No load, generation or weather forecast is
  an input for power. The target day's published generation forecast does not appear to be
  available before the 09:30 UTC lock (one observation, task T222b measures it), so this may be
  a limit of the question design and not only of the model.
- **Slices differ.** The slice card (Backtests page) shows months and day types where the
  advantage over "same as last time" is not supported; averages hide that.
- **The current model may have seen part of the comparison window**, which favours it; the
  rule is conservative for challengers.

## Ten interview questions

1. **How do you make sure the model never sees the future?**
   Three layers: the as-of gateway only releases data available at forecast time; training
   cut-offs are before the batch day; validation is an expanding window with a gap. The
   backtest uses the production code, so a leak would have to exist in production too.
2. **Why not shuffle for cross-validation?**
   Prices of neighbouring days are strongly correlated. A shuffled split lets the model train
   on days right next to the test day and gives an optimistic score that does not survive live.
3. **What is calibration and how do you do it?**
   A forecast of 70% should be right about 70% of the time. I fit a logistic (Platt) map on
   out-of-fold predictions of earlier questions and check reliability diagrams and the
   expected calibration error. A well-ranked but miscalibrated model still scores badly.
4. **Why quantile regression and not a classifier per threshold?**
   Thresholds change daily. One set of quantile models covers every threshold, and the
   probability follows from the predicted distribution.
5. **How does a model get promoted?**
   Weekly, a candidate is trained with a cut-off before the last 28 days, both it and the
   current model are scored on those days' real questions, and it is promoted if its Brier
   score is not worse. The decision and numbers are public.
6. **The PyTorch model lost. Why keep it?**
   Because the result is information: on 365 days of a few features, a small network was not
   better than boosted trees. Publishing the negative result shows the comparison was fair.
7. **How do you know which model produced a forecast?**
   Each forecast stores the version string and the artifact's SHA-256; the registry on the
   ledger branch holds the file, its metadata and the promotion record.
8. **What happens if the model file is corrupt?**
   The loader checks the hash. On failure, `ml` writes a skip with the reason for that domain;
   the health check flags missing ML forecasts and an incident opens. A skip is never 0.5.
9. **Is the weather model "machine learning"?**
   Not yet: it is a documented rule set on the official forecast, fixed before any live
   question resolved. A learned model needs a history of past forecasts as they were issued,
   which the morning snapshots are building.
10. **What would you improve first?**
    Test whether the generation and load forecasts are published early enough to be features
    at all, then archive them with their publication time; only if they are, run an ablation
    as a new challenger through the same weekly rule. Without that, adding them would be
    leakage.
