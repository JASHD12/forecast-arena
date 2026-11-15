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

## Weekly evaluation

Window 2026-10-16 to 2026-11-12, 224 questions; candidate Brier 0.10534384750520383, current None.
