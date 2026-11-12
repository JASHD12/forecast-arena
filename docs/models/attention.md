# Model card: `ml` for attention (attention-hgb, revision 1)

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

## Backtest (run `attention-2026-10-15-2026-11-07-20261112T1538`)

**BACKTEST** (not part of the live record).

Batches 2026-10-15 to 2026-11-07 (24 batch days).
Observed YES rate on scored questions: 0.500 (a constant forecast of that rate would score Brier 0.2500).

| Forecaster | n | Brier | 95% interval | Log score |
|---|---|---|---|---|
| base_rate | 192 | 0.2500 | [0.2500, 0.2500] | 0.6931 |
| persistence | 192 | 0.2500 | [0.2500, 0.2500] | 0.6931 |
| ml | 192 | 0.1101 | [0.0811, 0.1420] | 0.3742 |

Paired Brier differences (negative = first is better), day-block bootstrap, 2000 replicates, fixed seed:

| Comparison | Difference | 95% interval | Supported? |
|---|---|---|---|
| ml - base_rate | -0.1399 | [-0.1689, -0.1080] | yes |
| ml - persistence | -0.1399 | [-0.1689, -0.1080] | yes |

Notes:

- ml = gradient-boosted classifier on the article's 7-day top-list trajectory, K, project and weekday; Platt calibration on out-of-fold predictions; retrained every 28 days on the previous 60 reference days whose labels were published by the batch morning.
- base_rate and persistence are per article (SPEC 8.1/8.2); articles rarely repeat, so both answer 0.5 here.
- Training labels come from top lists only (rows whose label the lists cannot decide are dropped); questions are resolved with the real per-article API.
- The backtest domain does not apply the 'not used in the previous 3 batches' exclusion.
