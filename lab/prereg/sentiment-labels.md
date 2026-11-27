# Pre-registration: open sentiment model against Claude labels on crypto headlines (T375)

Experiment id: `sentiment-labels`. Registered 2026-11-27, **before any paid call**. No forecaster uses headline sentiment (the
`sentiment` forecaster uses GDELT's own tone numbers, `lab/prereg/sentiment.md`), so this is a stand-alone measurement of a tool
choice: can a small open model on a CPU replace an LLM labeller for crypto headlines, and what does each cost?

## Data (fixed now)

- 500 English-language headlines from the GDELT DOC 2.0 article list (`mode=artlist`), 100 per coin of the five coins of SPEC 7.5
  (the fixed queries of `lab/prereg/sentiment.md`), published in the 7 days before the run, sampled with seed 0.
- **Titles only.** A title is scored by both raters in memory and discarded: no title, URL or outlet is written to any file, log
  or result (S7, S12). Only counts, agreement numbers and token usage are kept.

## Raters (fixed now)

- **Open model:** `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis` (Apache-2.0, pinned revision in
  `docs/SOURCES.md`) through ONNX Runtime on the CPU. Its score P(positive) - P(negative) is mapped to 1..5 with the fixed bins
  [-1, -0.6) = 1, [-0.6, -0.2) = 2, [-0.2, 0.2] = 3, (0.2, 0.6] = 4, (0.6, 1] = 5.
- **Claude Haiku** (the model id is recorded in the result): one request per headline, a fixed rubric in
  `src/arena/lab/sentiment_labels.py` (1 = very negative for the coin's price outlook, 5 = very positive, 3 = neutral or not about
  price), answer a JSON object with an integer `rating`. No examples, temperature as configured, no retries other than one repair
  request per unparseable answer.

## Metrics

Quadratic-weighted kappa between the two raters (`arena.lab.judge.weighted_kappa`), exact agreement, three-class agreement
(1-2 negative, 3 neutral, 4-5 positive), the distribution of each rater's ratings, tokens and list-price cost per 1,000
headlines for Claude (None if the model has no price in the table), CPU time per 1,000 headlines for the open model. Headlines for
which Claude's answer cannot be parsed are counted and excluded (never filled).

## Hypotheses

- **H-SL1:** the weighted kappa is at least 0.50.
- **H-SL2:** the Claude cost per 1,000 headlines is at most US$0.20.
- Descriptive only: three-class agreement and where the raters disagree most (counts by rating pair, no text).

## Not tested (and why)

The plan's idea to re-run the sentiment backtest with Claude labels is dropped: the pre-registered forecaster does not use
headline sentiment, and GDELT's article list has no history to label.

## Decision rule

Whatever the numbers, they are published with the sample size. Nothing live changes (I8). Cost: about 500 requests of about 300
tokens (about 150,000 tokens), hard cap 400,000 tokens and 600 requests; the lab budget has US$0.32 left
(`docs/project/LAB_BUDGET.md`). The run needs the owner's OK (HUMAN_TODO H45) and runs once, from `main`.
