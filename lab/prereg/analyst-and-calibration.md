# Pre-registration: `agent_analyst`, a calibrated copy of `llm_context`, and replay on weather and Wikipedia (T381)

Experiment id: `analyst-and-calibration`. Registered 2026-11-27, **before any paid run and before the calibration map was fitted** (SPEC 17,
rule L2). Evaluation only: nothing here changes `ml`, `llm_context`, `agent`, `agent_graph` or any other live forecaster, prompt, threshold or
version (I8); every new forecaster is a new id. The goal is a fair contest, not a forced win for the AI: the project's hypothesis H1 says the
classical model wins on numeric topics and the data so far agree, so negative results are expected and will be published.

## Why

Questions answered by `ml`, `llm_context` and `agent` so far (live record, rehearsal and official days): the whole gap in favour of `ml` is on
weather and electricity; the models hedge (mean |p - 0.5| is 0.24 for `ml`, 0.22 for `agent`, 0.21 for `llm_context`); the agent seldom calls
its tools and has never called `get_ml_forecast`. Two cheap ideas follow, neither tested yet:

1. `agent_analyst` (built, off, prompt `agent_system_v4`) starts from the `ml` forecast and changes it only for evidence the model cannot see.
2. A monotone recalibration of `llm_context`'s answers (a logit slope and intercept, "extremizing") may remove part of the hedging at zero token cost.

## Frozen data (sets fixed before any run; hashes go into every result)

- **Power, November** `evals/golden/power-2026-11a.jsonl` (90 questions, sha256 `fd31d14b...`), with replayed `ml` probabilities
  `evals/golden/ml-probs-power-11a.json` (a walk-forward replay of the production power model; replay, not live).
- **Power, October** `evals/golden/power-2026-10.jsonl` (186 questions, sha256 `29939ca9...`) with `evals/golden/ml-probs-power.json`.
- **Live days, weather and Wikipedia** `evals/golden/replay-weather-attention-2026-11-25.jsonl` (232 questions: 152 weather, 80 Wikipedia
  attention; batch days 2026-11-15 to 2026-11-25; sha256 `4bd18abc...`, label "replay of live days"). Contexts are the exact morning
  snapshots the live forecasters saw, including the stored DWD MOSMIX forecast; the `ml` arm is the **live** `ml` forecast of that morning
  (read from the ledger, not recomputed). The set is a test set only: no prompt, tool, threshold or map is chosen by looking at it (I8).
- **Calibration training data** (free, already stored): Claude Haiku's `llm_context` probabilities for 1,198 template-balanced questions of the
  lab **training** split (`lab/data/distill-labels-v1.json`, same prompt as the live `llm_context`), with outcomes from
  `lab/data/forecast-sft/train.jsonl.gz`. Live outcomes are never used to fit anything.

## Arms and the calibration map (fixed now)

- `agent_analyst`, `agent_quant`, `agent_skills`: the existing replay variants with their current prompts, tools and a limit of four research
  calls. `agent` (replay version of the live agent) is reused from run `eval-20261126T195707` on the same 90 November items (hash checked).
- `llm_context` raw: one new run of the live prompt on the same items. **`llm_context_cal`**: the same answers passed through
  `p' = sigmoid(a * logit(p) + b)`, with `a` and `b` fitted once by unpenalised logistic regression on the 1,198 training answers (probabilities
  clipped to [0.01, 0.99]). No other map, no refit, no choice among maps. The map is fitted on power questions only, so any live use would apply
  it to power questions only and pass other topics through unchanged.
- Subset rule for weather and Wikipedia (if run): 60 weather and 60 Wikipedia questions of the replay set, seeded stratified by day with seed 0.

## Budget (the lab budget has US$0.32 left, `docs/project/LAB_BUDGET.md`; the owner decides the tier, HUMAN_TODO H46)

Estimates from the cost per question of earlier runs (agent about US$0.0006, agent_quant 0.0011, agent_skills 0.0014, llm_context 0.0005):

| Tier | What | Estimate |
|---|---|---|
| A | `agent_analyst` and raw `llm_context` on the 90 November power questions | about US$0.13 |
| B | adds raw `llm_context` on the 186 October questions (a second test of the map) | about US$0.10 more |
| C | adds `agent_quant`, `agent_skills`, `agent_analyst` on the 120-question weather and Wikipedia subset | about US$0.40 more |

Tier A fits the remaining budget; B and C need a new budget decision. Each tier is run once, from `main`, with a hard token cap, and only with
the owner's OK. The Part 1 label comparison (`lab/prereg/sentiment-labels.md`, at most about US$0.10) draws on the same budget.

## Hypotheses

Confirmatory (power, November items; three tests, no multiplicity correction, stated):

- **H-A1**: `agent_analyst` is not worse than `ml`: the 95% day-block interval of Brier(analyst) minus Brier(ml) is not entirely above zero.
- **H-A2**: `agent_analyst` has a lower Brier than `agent` (interval below zero).
- **H-C1**: `llm_context_cal` has a lower Brier than raw `llm_context` (interval below zero).
- **H-A3** (cost): `agent_analyst` costs less per answered question than `agent_skills` (US$0.0014 in run 45883972017).

Secondary and descriptive: H-C1 repeated on the October items (tier B); the fitted `a` and `b` (a slope above 1 means the raw answers were too
timid), reliability of raw and calibrated answers, the mean |p - 0.5| of each arm; Brier **per topic** for every arm with paired intervals against
`ml` and the base rate; **weather** (tier C): `agent_analyst` not worse than `ml` on weather (H-W1) and, expected, `agent_quant` and
`agent_skills` not better than `ml` on weather (H-W2, H1). Nothing is confirmatory on Wikipedia (the replay has no news backend, stated on the card).

## Decision rule

Whatever the numbers, they are published with intervals, sample sizes, per-topic tables and cost per answered question.

- `agent_analyst` becomes a launch candidate (experimental, outside the headline board and the ensemble) only if H-A1 and H-A3 hold and a dry run
  stays within the 300,000-token daily cap; the owner decides.
- `llm_context_cal` becomes a launch candidate (experimental, zero extra tokens, power questions only) only if H-C1 holds.
- Weather and Wikipedia results decide nothing by themselves; a variant is judged on weather live after at least 30 official days.
- A negative result stays on the card and the Lab page. The evaluation is run once per tier.

## Limits stated now

The November power set has already been used by other variants (`agent`, `agent_quant`, `agent_skills`, the committee), so it is a shared test set,
not a fresh one. The replay has no news or Wikipedia backend and no retriever; tool calls to them are recorded as errors. The 232-question live-day
set is small, days are correlated (the intervals are day-block), and rehearsal days are included.

## Addendum 2026-11-27 (before any run): coverage of the live `ml` arm

The live `ml` forecast exists for 209 of the 232 live-day questions (`evals/golden/replay-weather-attention-2026-11-25.ml-probs.json`; the other 23 have
no `ml` forecast in the ledger). Paired comparisons against `ml` on that set use only the 209 questions; comparisons that do not involve `ml` use all of them.
No missing probability is filled in.
