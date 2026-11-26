# Pre-registration: numeric tools and an ML-aware prompt for the tool-using agent (T340)

Experiment id: `llm-quant`. Registered 2026-11-26, before any new forecaster has run (SPEC 17, rule L2). Evaluation only: nothing here
changes `agent`, `agent_graph`, `llm_context` or `llm_plain` (integrity rule I8); the new forecasters are new ids with their own versions.

## Why

On the 86 live questions all five common-set forecasters answered (9 days, rehearsal and official), the tool-using agent loses to the
`ml` model on weather (0.131 vs 0.086) and electricity (0.182 vs 0.137), ties or wins on Wikipedia attention (0.061 vs 0.065) and trails on
currencies (0.282 vs 0.248; nobody beats the base rate there). All intervals overlap at this sample size. Two observations suggest a fair
fight has not happened yet:

1. The agent is less sharp than `ml` (mean |p - 0.5| 0.230 vs 0.246) and hedges toward the base rate; its most used tools are
   `get_base_rate` (72 of 588 stored traces) and `similar_past_questions` (58), both reference classes that pull toward the base rate.
2. It has had a `get_ml_forecast` tool since the first version and **never called it** (0 of 588 traces); the system prompt does not mention it.

## The two new forecasters (both experimental, same model, same daily sample, same tool-call limit of 4)

- `agent_quant`: the agent's loop plus two read-only numeric tools, `estimate_probability` (a documented reference estimate computed from
  the stored as-of context and the question only) and `calculate_probability` (a normal-distribution calculator), with a prompt that asks for
  a numeric estimate first and an adjustment for evidence second.
- `agent_analyst`: the existing tools and a prompt that tells the agent to start from `get_ml_forecast` and to change that number only for
  evidence the model cannot see (news, Wikipedia events, holidays, outages) and to say which.

## Method

- Items: the frozen power sets `evals/golden/power-2026-10.jsonl` and `power-2026-11a.jsonl` (276 questions, built before any run; sha256
  recorded in the result), a seeded stratified subset of at most 100 items to fit the lab budget (see `docs/project/LAB_BUDGET.md`).
- Arms on identical items: `agent` (the live prompt and tools, replay version), `agent_quant`, `agent_analyst`, plus `ml` (replayed
  probabilities in `evals/golden/ml-probs-power.json`, built with the free power backtest) and the golden base rate.
- Replay limits, stated on the card: no news or Wikipedia backend, no retriever; a call to those is recorded as a tool error.
- Metrics: Brier and log score, share of valid answers, tokens and estimated cost per question, paired day-block intervals
  (`arena.scoring.stats`) on identical item sets.

## Hypotheses

- **H-Q1**: `agent_quant` has a lower Brier than `agent` on these items (paired interval below zero).
- **H-Q2** (expected): `agent_quant` does **not** beat `ml` on electricity (H1 of the project).
- **H-Q3**: `agent_analyst` is not worse than `ml` (interval against `ml` includes zero or is below it). Without news in the replay this
  mostly tests whether the agent overrides a good number for no reason.
- **H-Q4** (descriptive, expected): on weather the numeric estimate is the `ml` rule itself (a fixed normal error around the MOSMIX forecast,
  `weather-rules-r2`), so a numerate agent can at best match `ml` there. Weather cannot be replayed (no MOSMIX archive), so it is judged only
  on live days, after at least 30 official days, never on the replay.

## Decision rule

All results are published with intervals and sample sizes, negative ones included. A new forecaster goes live (experimental, outside the
headline board, outside the ensemble) only if H-Q1 holds on at least 80 items and its cost per question is within the 300,000-token daily cap
(measured in a dry run first); otherwise it stays off and the card says why. No live forecaster, prompt or threshold changes because of how a
specific live question resolved (I8). Evaluated once.
