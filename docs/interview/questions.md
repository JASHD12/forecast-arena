# 40 likely questions, with honest answers

Numbers: only those in [numbers.md](numbers.md), always with their kind (backtest,
evaluation, live). "I don't know yet" is a good answer when the record is too short.

## The project

**1. What is it, in one sentence?**
A public benchmark where baselines, a classical ML model and several LLM forecasters
publish probabilities on yes/no questions about tomorrow before the answer exists, and
are scored when the official data arrives.

**2. What question are you trying to answer?**
When an LLM agent beats a classical model at forecasting, and when it does not. "It does
not" is an acceptable result; the system is built so it can say that honestly.

**3. Why forecasting, and why these data sources?**
Forecasts can be scored objectively and cannot be faked after the fact, unlike most LLM
demos. German electricity prices, DWD weather, Wikipedia pageviews and ECB exchange rates
are free, public, published on a fixed schedule and have clear licences.

**4. What does a question look like?**
"Will the German/Luxembourg day-ahead price for <day> have a daily mean above X EUR/MWh?",
where X comes from the recent past (for example the median of the last 28 days), so the
answer is genuinely uncertain. The exact resolution rule is stored with the question.

**5. What is live today and what is not?**
Electricity questions run live every day with the baselines and the LLM forecasters. The
gradient-boosted model, the other topics, the ensemble and the players' leaderboard are
built and tested, and switch on as their tasks complete. The site and `TASKS.md` say which.

## Integrity

**6. How do you prove a forecast was made before the answer existed?**
Every question has a lock time. Forecasts are appended to a JSONL ledger on a public git
branch, the batch files are hashed into a batch seal before the lock, and each day is
sealed into a hash chain. `arena ledger verify` checks every forecast's time against its
lock and recomputes all hashes; `--git` also checks the commit times.

**7. Git timestamps can be faked. Isn't that a hole?**
Yes, they are evidence, not proof; the methods page says so. What makes a silent edit
detectable is the combination: the public branch history that every clone keeps, the
hash chain, and the GitHub Actions logs, which I cannot edit.

**8. What is the as-of gateway?**
Every stored value carries the time it became public. Forecasters receive data only
through a function that filters on that time. That prevents leakage live and makes
backtests honest, because a replayed day sees only what was public then.

**9. What happens when a model fails?**
It records a skip with a reason code (`parse_failure`, `budget_exhausted`, `error`,
`not_sampled`). It never inserts 0.5. Skips are visible on the question pages.

**10. Why append-only? What if you make a mistake?**
Because a record you can edit is not a record. Corrections are new records that say what
they correct. Example: when the live agent failed on the first day, the error skips stay
in the ledger; the fix only affects later days.

**11. How do you avoid tuning on the live results?**
Models, prompts and thresholds change only through versioning and backtests, never
because a particular live question went wrong. Every version appears in the changelog
on the Methods page, and the official record starts only after the changes settle.

## Machine learning

**12. How does the ML model produce a probability?**
It predicts quantiles of the next day's price statistic with gradient-boosted quantile
regression, interpolates them into a distribution, reads off P(statistic > threshold),
and calibrates that probability. One model answers every threshold question consistently.

**13. Why quantile regression rather than a classifier per question?**
Thresholds change every day; a classifier per template would waste data and could give
inconsistent answers for two thresholds on the same day. Modelling the distribution
once keeps answers coherent.

**14. How good is it?**
In the one-year electricity backtest the ML model's Brier score is 0.1930 against 0.2466
for the base rate; the paired difference is -0.0536 with interval [-0.0655, -0.0414].
That is a backtest, not the live record.

**15. Did LightGBM beat it? The PyTorch network?**
In the same backtest the Optuna-tuned LightGBM challenger scored 0.1884, a small but
supported improvement over the champion (-0.0045, [-0.0069, -0.0021]). The PyTorch
network scored 0.1927, a difference of -0.0003 whose interval includes zero: no evidence
it is better. The weekly job promotes a challenger only by its written rule.

**16. And the time-series models, including a foundation model?**
All lost to the champion: Chronos-Bolt 0.2142, SARIMAX 0.2279, ETS 0.2441. Chronos beat
the base rate; ETS did not (its interval includes zero). Generic univariate forecasting
loses to features built for the auction.

**17. How do you validate without leakage in time series?**
Walk-forward: train only on days before the forecast day, with a gap, the same way the
live system would have seen it. Optuna tunes with time-ordered folds and a 7-day gap.

**18. How do you compare two forecasters fairly?**
Only on the same questions (paired), with a day-block bootstrap interval because
questions on the same day are correlated, and in backtests a Diebold-Mariano test as a
second opinion.

**19. What is the Brier score and why use it?**
The mean squared error between the probability and the 0/1 outcome. It is a proper
scoring rule: you score best by reporting what you believe. Always saying 50% scores
0.25. The log score is reported too; it punishes confident mistakes harder.

**20. What is calibration and how do you show it?**
Of all the times a forecaster said "seven in ten", about seven in ten should come true. The site shows
reliability diagrams, the expected calibration error and the Murphy decomposition.

**21. What is the base rate forecaster and why must it be on every board?**
The smoothed YES share of past instances of the template. It is the bar any model must
clear; a leaderboard without it hides whether anyone learned anything.

**22. Why did the markets model not beat the base rate?**
Daily exchange-rate moves are close to unpredictable from public data; the backtest
difference is -0.0013 with an interval including zero. Reporting that is the point.

## LLMs

**23. Which LLM forecasters are there, and what does each see?**
`llm_plain` sees only the question; `llm_context` also gets the data summary; `agent` can
call read-only tools (data series, base rate, ML forecast, news headlines, Wikipedia
summaries, and with prompt v2 similar past questions);
`agent_graph` is the same idea as a LangGraph state machine; `llm_local` is a small
open-weights model run with llama.cpp on the runner. Same output contract for all.

**24. How do you make LLM output reliable?**
A strict JSON contract (probability, short rationale, key factors), strict parsing, one
repair attempt, then a recorded `parse_failure` skip. The local model uses a JSON grammar.

**25. Tell me about the evaluation harness.**
A frozen golden set of resolved past questions, run by a manual workflow against the real
model within the daily cap. It reports Brier against the base rate on the same items,
valid-JSON rate, repair rate, cost and stop reasons, and stays separate from live scores.

**26. Did it catch anything?**
Yes. The first run showed valid JSON on the first try for only 17% of `llm_plain` answers;
the stop reasons showed the 400-token output cap was cutting answers off while the model
was still thinking. After raising the cap to 1024 (configurable, and part of the version
string) the rerun had 100% valid JSON first try for both forecasters.

**27. So does context help the LLM?**
In the second eval run `llm_context` scored 0.1946 and `llm_plain` 0.2557 on the same 12
items, but the paired interval [-0.0849, +0.2158] includes zero. Twelve items cannot
settle it; that is what the live record is for.

**28. How do you control cost?**
A guard around every client enforces a hard daily token cap; when it is hit the remaining
forecasts become `budget_exhausted` skips. The LLMs answer a daily sample of questions.
Real calls happen only in GitHub Actions; tests use a fake LLM and recorded fixtures.

**29. How do you handle prompt injection through tools?**
Tools are read-only and return data from our own gateway. The system prompt states that
tool output is data and that instructions inside it must be ignored, and the harness, not
the model, enforces the call and time limits.

**30. How does the RAG tool avoid leakage?**
It embeds past questions locally (ONNX, no API cost) and only searches questions whose
resolution was recorded before the forecast time, so it never sees an answer that was not
public yet.

**31. Why build the LangGraph agent if you already had a hand-written loop?**
To compare a framework agent with the hand-written loop on the same model, tools and
caps. It runs on our own client wrapper, so every call still goes through the budget guard
and the fake LLM works in tests.

**32. What is tracing used for?**
Every model call becomes a span: model, prompt version, tokens, latency, tool calls,
parse and repair outcome. That feeds the LLM observability page (calls, tokens, estimated
cost per day) and the trace panel on each question page.

**33. What was the hardest LLM bug?**
On the first live day every agent answer failed with an HTTP 400 about modified thinking
blocks. The adapter re-sent the previous assistant turn through a serializer that dropped
null fields; with tools in the request the API checks those blocks. The fix re-sends the
SDK's exact wire form, with a regression test.

## Engineering

**34. Why GitHub Actions and Pages instead of a server?**
Zero hosting cost, nothing to patch, and a public log of every run. The price is a daily
cadence and scheduled jobs that start late, which is why every job runs twice and is
idempotent.

**35. How do you keep the scheduled jobs safe?**
They run code from a `stable` branch that only receives commits that passed CI. A shared
concurrency group allows one ledger writer at a time. Health checks after each job open
or close an incident issue.

**36. What does idempotent mean here and how did you test it?**
Running a job twice for the same date writes nothing the second time; a crash leaves no
partial file (temp file, validate, atomic rename). The offline end-to-end test runs a
multi-day schedule twice and compares every file byte for byte.

**37. What is the FastAPI service, Docker and Kubernetes for, if the site is static?**
A read-only REST API over DuckDB for people who want queries; it is built into a Docker
image and smoke-tested in CI, and the Kubernetes manifests are applied to a throwaway kind
cluster in CI. It is validated in CI, not hosted; the site says so.

**38. Where do dbt and Airflow fit?**
dbt builds staging and mart models with tests over the open Parquet export, run in CI.
The Airflow DAGs mirror the GitHub schedule and are parsed with DagBag in CI to show the
pipeline could move; production scheduling stays on GitHub Actions.

**39. What would you do differently?**
Start the live record earlier with fewer forecasters, because calendar time is the
bottleneck for results; and test against the real provider API in a cheap smoke workflow
from day one, which would have caught the thinking-block bug before the first live run.

**40. What did you learn?**
That most of the work in an honest evaluation is the plumbing around the model: data
timing, versioning, failure handling and statistics. And that saying "too early to tell"
on a public site is uncomfortable but correct.
