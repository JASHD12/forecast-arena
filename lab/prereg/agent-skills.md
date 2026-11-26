# Pre-registration: forecasting skills for the tool-using agent (T350)

Experiment id: `agent-skills`. Registered 2026-11-26, before `agent_skills` has run (SPEC 17, rule L2). Evaluation only: nothing here changes
`agent`, `agent_graph`, `agent_quant`, `agent_analyst`, `llm_context` or `llm_plain` (integrity rule I8). It follows `lab/prereg/llm-quant-tools.md`
and uses the same items, caps and metrics, so the arms can be compared.

## What is tested

`agent_skills` is `agent_quant` (reference estimate and probability calculator) plus one more tool, `load_skill`. The prompt shows a one-line
index of the available skills; the model may load the full text of at most two skills per question (these loads do not use the four research
calls, so the research budget equals `agent_quant`'s). A skill is a short, procedural note in the repository (`src/arena/agent/skills/<name>/SKILL.md`):
how to approach one topic, which tools to use for it, and a table of base rates computed by code from data before 2026-11-01. The comparison that
isolates the skills is `agent_skills` against `agent_quant`.

## Rules for skill content (so the experiment cannot leak)

- Skills contain general domain knowledge and statistics computed by `scripts/skill_tables.py` from backtest rows that end on 2026-10-31, with the
  source run and cut-off named in the file. No number is typed by hand. Nothing is chosen or worded because of how a live question resolved (I8).
- Any edit to a skill changes the forecaster's version string (a fingerprint of all skill files is part of it), so every version is visible.
- The frozen power set `evals/golden/power-2026-10.jsonl` covers target days in October 2026, which are inside the tables' window. The tables hold
  aggregate base rates by weekday and template over a year, not per-question answers; the leak is judged small but real, so the evaluation
  reports the result **also on the 90 questions of November 2026** (`evals/golden/power-2026-11a.jsonl`, outside the window) as the cleaner
  comparison, and the decision rule uses that subset first.

## Method

- Items: `power-2026-11a.jsonl` (90 questions, primary) and a seeded stratified subset of `power-2026-10.jsonl` (secondary, at most 60 items), same seed as
  the `agent_quant` run. Arms on identical items: `agent`, `agent_quant`, `agent_skills`, plus the replayed `ml` probabilities and the golden base rate.
- Replay limits as before (no news or Wikipedia backend, no retriever), stated on the card.
- Metrics: Brier, log score, valid-answer share, tokens and cost per question, paired day-block intervals on identical items
  (`arena.scoring.stats`), and which skills were loaded and how often (from the traces).

## Hypotheses

- **H-S1**: `agent_skills` has a lower Brier than `agent_quant` on the November items (paired interval below zero).
- **H-S2**: its cost per question is at most 30% higher than `agent_quant`'s.
- **H-S3** (descriptive): the agent loads the skill for the question's topic (power) in most questions; loads of the core skill are reported.
- **H-S4** (expected): no benefit on weather, Wikipedia, currencies and crypto can be shown on the replay because those topics cannot be replayed
  faithfully; they are judged only on live days after at least 30 official days, never on the replay.

## Decision rule

Results are published with intervals and sample sizes, negative ones included. `agent_skills` goes live (experimental, outside the headline board and
the ensemble) only if H-S1 and H-S2 hold and a dry run stays within the 300,000-token daily cap; otherwise it stays off and the card says why.
No live forecaster or prompt changes because of how a specific live question resolved (I8). The evaluation is run once.

## Addendum 2026-11-26: the graph and hybrid variants (T357, T358)

`agent_graph_skills` and `agent_hybrid_skills` add the same three tools (`estimate_probability`, `calculate_probability`, `load_skill`) to the LangGraph agent
and to the hybrid-retrieval agent. They have **no offline evaluation**: the replay harness has no LangGraph runtime, retriever or reranker, and weather,
Wikipedia, currencies and crypto cannot be replayed. They therefore follow the decision rule above indirectly: they are launched (experimental, outside the
headline board and the ensemble) only if `agent_skills` passes its evaluation, and then judged live, on the same sampled questions against their base
forecaster (`agent_graph`, `agent_hybrid`), after at least 30 official days. Nothing about them changes because of how a specific live question resolved (I8).
