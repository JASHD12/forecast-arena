# Pre-registration: the tool-using agents on weather and Wikipedia attention, a replay of live days (Tier C)

Experiment id: `tier-c-weather-attention`. Registered 2026-11-28, **before any model call of this experiment and before the sampler
and workflow option it needs exist**. Evaluation only (SPEC 17): nothing here changes a live forecaster, prompt, threshold or version
(integrity rules I4 and I8), and the replay set is a test set that no prompt, tool or threshold is chosen on.

## Why

The electricity evaluation (`docs/lab/agent-quant-r2.md`, `agent-skills-r2.md`, `analyst-and-calibration.md`) tested the tool-using agents on
the one topic where the classical model is expected to win (the project's H1) and where a replay has no news or retriever. Its intervals
were too wide for effects of about 0.005 Brier. Wikipedia attention is the news-driven topic where an agent could plausibly beat `ml`
(live record so far: the agent 0.079 against `ml` 0.088, intervals overlapping); weather is the topic where `agent_quant`'s estimate is the
`ml` rule itself, so no gain is expected there. This is the pre-registered test of both on days the live forecasters actually saw.

## Data (frozen before the run)

- `evals/golden/replay-weather-attention-2026-11-25.jsonl` (232 questions, 152 weather and 80 Wikipedia attention, batch days 2026-11-15 to
  2026-11-25, sha256 `4bd18abc...`, label "replay of live days"). Contexts are the exact morning snapshots the live forecasters saw. The
  `ml` arm is the **live** `ml` forecast of each question's morning, read from the ledger
  (`replay-weather-attention-2026-11-25.ml-probs.json`, 209 of 232 questions have one; it is not recomputed).
- **Subset:** 60 weather and 60 attention questions among those that have a live `ml` forecast, so every arm can be compared with `ml`.
  Within each topic the questions are drawn round-robin across batch days from a seeded shuffle (seed 0), by `--per-topic 60` of
  `arena eval run`. The subset is fixed by this rule and the seed, not by looking at any answer.

## Arms (identical questions, same model, same tool-call limit of 4)

`agent` (the replay version of the live agent), `agent_quant` r2, `agent_skills` r2, `agent_analyst`, and the live `ml` forecast. In the
replay there is no news backend and no retriever (a call is a recorded tool error). The replayed `ml` probabilities are passed to every
arm, as `agent_analyst` needs them; `agent`, `agent_quant` and `agent_skills` can therefore call `get_ml_forecast`, which they did not
in the electricity run (they never called it in 588 stored traces). The run's token cap is 4,500,000, chosen from the per-question
tokens of the electricity runs plus 15%; a question skipped because the cap ran out is reported as such and not counted against a forecaster.

## Hypotheses (per topic; paired day-block 95% intervals on the questions both arms answered)

Confirmatory, nine tests (three arms against `ml` and three against `agent`, on two topics, counted as the families below; no multiplicity
correction, stated):

- **H-T1**: on weather and on attention, `agent_analyst` is not worse than `ml` (the interval of Brier(analyst) minus Brier(ml) is not
  entirely above zero).
- **H-T2**: on attention, each of `agent_quant`, `agent_skills` and `agent_analyst` has a lower Brier than `agent` (interval entirely below
  zero).
- **H-T3** (descriptive, expected): on weather `agent_quant` is not different from `ml` (its estimate is the `ml` weather rule).
- **H-T4** (cost): each arm costs at most 1.75 times `agent` per question asked.

## Decision rule and limits

Tier C alone launches nothing and switches nothing off: it is a replay and informs the live comparison (`lab/prereg/live-agents-comparison.md`),
which decides. All results are published with intervals, sample sizes and per-topic tables, negative ones included. One run, once. Limits:
60 questions per topic from 11 days (the questions of a day are correlated, so intervals resample whole days); replayed tools only; the
questions were seen by the live forecasters (their live answers exist), but no arm here was tuned on them.

## Cost

About US$0.50 (the per-question cost of the four arms in the electricity runs is about US$0.0041 together, times 120; weather and attention
contexts may be longer), worst case about US$0.59 at the token cap. The lab limit is raised to US$3.00 by the owner's decision of 2026-11-28
(US$2.41 spent before this run); the run is dispatched from `main` only after the owner's OK.
