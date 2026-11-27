# Pre-registration: the GDELT news-tone forecaster `sentiment-gdelt-r1` (T370)

Experiment id: `sentiment`. Registered 2026-11-27, **before any sentiment feature was computed or any backtest of this forecaster was
written** (SPEC 17, rule L2). The commit that adds this file precedes the commit that adds the backtest code; the result file carries this
file's SHA-256.

## Why, and what we expect

The owner wants a forecaster that uses what is said online. Published research finds that social and news sentiment has at best weak
next-day predictive power for crypto. We therefore expect **little or no skill**; "no skill" is a valid, publishable result (as H3 is for
currencies). Reddit is not used (HUMAN_TODO H44 and DECISIONS 2026-11-27); the GDELT+Reddit hypothesis H-SE3 is parked.

## Data (fixed now)

- Outcomes: the CoinGecko daily 00:00 UTC prices of the five coins of SPEC 7.5, the recorded history in `tests/fixtures/coingecko/`
  (365 days to about 2026-11-12). Only days up to **2026-10-31** are used. The Demo API reaches back only 365 days, so there is **no
  held-out year**: the test period is the last part of one year (stated as a limit on the card).
- Questions and thresholds: the arithmetic of `arena.domains.crypto` (`bigmove` threshold = median |daily log return| over the last 60
  known days, rounded to 0.001; `up` = return > 0).
- Features, GDELT DOC 2.0 only (daily steps, `mode=TimelineTone` and `mode=TimelineVolRaw`, one fixed query per coin, English sources):
  bitcoin `bitcoin sourcelang:english`; ethereum `ethereum sourcelang:english`; solana `solana crypto sourcelang:english`; ripple
  `(xrp OR ripple) crypto sourcelang:english`; binancecoin `("binance coin" OR bnb) sourcelang:english`. Changing a query needs a new version.
- As-of rule: the value of UTC day X counts as known from X+1 12:00 UTC (a 12-hour publication lag, conservative). A question locked at
  09:30 UTC on B therefore uses days up to **B-2** only (I3).
- Features of the question (three, all from days <= B-2): `tone` (daily average tone), `tone_chg` (tone minus its mean over the 7 days
  before), `vol_chg` (ln of article count divided by its 7-day mean). Standardised with the training window's mean and spread. For
  `bigmove` a fourth feature is `logit(p_ml)`, the probability of `ml` (`crypto-ewma-t5-r1`) for the same question.

## Method (fixed now, not tuned on the test period)

- Model: one L2 logistic regression (C = 1.0, lbfgs) per template (`bigmove`, `up`), pooled over the five coins.
- Walk-forward, expanding window: the first test day is the 120th day of the history; refit every 7 days on all earlier resolved days;
  predictions only for days after the training window ended (gap of 2 days). No other hyperparameter is searched.
- Arms on identical questions: `sentiment`, `ml` (`bigmove` only), the base rate (Laplace, last 90 instances per coin and template), and 0.5.
- Metric: Brier. Paired differences with day-block bootstrap 95% intervals (`arena.scoring.stats.paired_brier_difference`).
  Per coin results are descriptive.
- Minimum size: at least 800 pooled test questions per template, else the result is reported as inconclusive.

## Hypotheses

- **H-SE1** (`bigmove`): `sentiment` has a lower Brier than `ml`: the interval of Brier(sentiment) - Brier(ml) lies entirely below zero.
  Expected: not met.
- **H-SE2** (`up`): the null. `sentiment` is **not** better than 0.5: the interval of Brier(sentiment) - 0.25 includes zero or is above it.
  Meeting H-SE2 means "no direction skill", the expected outcome. If the interval lies entirely below zero, it is reported as a surprise and
  gets a fresh-days check before anything else is said (multiple-testing caution: one test only).
- **H-SE3** (Reddit adds to GDELT): parked, not tested (needs H44 and 60 + 30 days of data).

## Decision rule

Whatever the numbers, they are published with intervals and sample size on the card and the Methods page, labelled "backtest" (I4). The
forecaster stays off (flag `ARENA_SENTIMENT`) unless H-SE1 is met; even then, going live needs a dry run within the token and runner-time
budget and the owner's OK, and it runs outside the headline board and the ensemble. Nothing live changes (I8).
