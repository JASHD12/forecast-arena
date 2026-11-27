# Crowd mood: news tone as a crypto forecaster (T370-T376)

Written 2026-11-27. The forecaster is a pre-registered **backtest only**; nothing here runs on the live record. The numbers are
in the generated card `docs/lab/sentiment.md` (copied from `evals/results/lab-sentiment.json`), not typed here.

## What it is

An experiment on one question: *does what the news says about a coin help to predict whether its price moves tomorrow?*
Published research finds at best weak next-day predictive power from social or news sentiment for crypto, so "no skill" was
written down as an expected, valid result before anything ran (`lab/prereg/sentiment.md`, committed before the backtest code).

Inputs, all aggregate numbers:

- **GDELT** (the GDELT Project's DOC 2.0 API): the average tone of English-language news matching a fixed query per coin, and
  the number of matching articles, per UTC day. Free to use with attribution.
- **`ml`'s probability** for the same question (the EWMA volatility model), as a fourth input for the "big move" question.

Model: one L2 logistic regression per question type, trained walk-forward (refit every 7 days on outcomes known that morning).
Version `sentiment-gdelt-r1`. It is judged against `ml`, the base rate and a flat 50%, on identical questions, with paired
day-block confidence intervals.

## How it avoids looking into the future (I3)

A GDELT day counts as known only 12 hours after it ended, so a morning forecast on day B sees days up to B-2 and no later.
A day with no articles has no tone and the question is skipped for every arm; a day in a chunk that was never recorded is
unknown, not zero. `ctx["gdelt"]` holds only these numbers, is stored in the morning snapshot when the flag
`ARENA_SENTIMENT` is on (off by default), and is hidden from the language-model forecasters' prompts.

## What was rejected, and why

- **X (Twitter)**: the API is paid per post read, needs an account and card, has no free history and its terms ban training
  foundation models on its content (SOURCES 2026-11-27).
- **Reddit**: its Data API terms restrict using content to train machine-learning models and its rate limits could not be read;
  the owner chose "no Reddit" (H44).
- **Scraping anything**: against the terms of the sites, so against rule S7.
- **Stocks**: licensed data and investment-advice rules; crypto only (a research benchmark, never advice).
- **Storing text**: only numbers are kept; no headline, post or user name is stored or shown (S7, S12).
- **A language model on the headlines as an input**: the open DistilRoBERTa model (Apache-2.0) is built and ONNX-exported with a
  parity check, but it has no history for a backtest, so it is not an input of this version. FinBERT was rejected on its
  licence (CC-BY-NC-SA).

## What it found

See `docs/lab/sentiment.md`. Whatever the numbers are, they are published with their intervals and sample size, and the
forecaster stays off unless the pre-registered rule is met and the owner agrees (I8).

## Ten questions an interviewer may ask

1. **Why GDELT and not Twitter or Reddit?** Cost, terms and history: X is paid with no free history; Reddit's terms restrict
   model training; GDELT is free with attribution and has years of daily data, so a backtest is possible before a live record.
2. **How do you know there is no look-ahead?** An explicit 12-hour publication lag, a test that no context contains a day after
   B-2, and a walk-forward that refits only on outcomes known that morning (also tested).
3. **Why pre-register an experiment you expect to fail?** Because "no skill" is only meaningful if the test, the model and the
   decision rule were fixed before looking. The hash of the pre-registration is in the result file.
4. **Why a logistic regression?** Few rows (about a year, five coins), noisy features, and a need to see the coefficients;
   anything larger would overfit and would not be interpretable.
5. **Why is `ml` an input?** Volatility is the strongest known predictor of "big move"; the question is whether news tone adds
   anything on top of it.
6. **What are the limits?** One year of prices (no held-out year), few articles per day for some coins, so a noisy tone, and
   missing history chunks (stated on the card).
7. **Does it give trading signals?** No. Research only; no advice, no trading (S1).
8. **What if the result looks good?** It is a single backtest on one year. I would run it on fresh days after 30 days of archived
   aggregates before believing it, and the owner decides about any launch.
9. **How is personal data handled?** None is collected: no post text, usernames or links, only per-day aggregate numbers.
10. **What would you do next?** Archive the daily aggregates live for 60 days and re-test, add the headline-level model only if
    it adds on that archive, and consider other sources only after reading their terms.
