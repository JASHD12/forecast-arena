# Pre-registration: `agent_skills` r2, a smaller skills index and skill text that matches the r2 estimate (T400)

Experiment id: `agent-skills-r2`. Registered 2026-11-28, **before any code of this version exists and before any model call**.
Nothing here changes a live forecaster (integrity rule I8): the forecasters are experimental and off, and the new revision strings are
visible in their versions. Builds on `lab/prereg/agent-quant-r2.md` (the `quant-r2` estimate); the committee follows (T401).

## Why

On the 90 November power questions `agent_skills` r1 did not meet its rules (`lab/prereg/agent-skills.md`):

- H-S1 (Brier below `agent_quant`, interval entirely below zero): the difference was -0.0090 with a 95% interval of [-0.0204, +0.0028].
  The interval includes zero; the point estimate favours skills.
- H-S2 (cost at most 1.30 times `agent_quant`): 1.31 times (US$1.3928 against US$1.0608 per 1,000 questions asked).

A read of the code and the stored token counts found:

1. The overrun is almost all input tokens (+3,081 per question against `agent_quant`, +48 output tokens). The system prompt carries an
   index of all six skills (1,032 characters) and is re-sent on both model calls of every question, and a loaded skill adds up to 2,960
   characters. About 138 input tokens per question less would have met H-S2.
2. The electricity skill tells the model that the r1 estimate "is a good anchor" for mean, max and evening and says nothing about
   `up_vs_today`, whose r1 estimate was mis-specified. The skill text therefore reinforced the weak estimate (`quant-r2` replaces it).
3. The evaluation harness does not save the tool traces, so H-S3 (which skills were loaded, how often) could not be measured.

Disclosure: the author had seen the November aggregate results of r1 when choosing these changes. The changes are mechanical (a
smaller prompt, text brought in line with a changed estimate, a measurement that was missing); the skill text uses only material up to
2026-10-31 (the generated base-rate tables, `skills.CUTOFF`).

## Changes (revision `skills-r2`)

- **Index by topic.** The system prompt lists only the skills whose topics include the question's domain, plus `forecasting-core`
  (topics `all`), instead of all six. `load_skill` still accepts any skill name.
- **Electricity skill, revision 2.** The tool guidance matches the r2 estimate (persistence with a normal error: it does not know the
  weekday pattern or the hourly shape of the latest day); the weekday table is pointed at for `up_vs_today`; the "good anchor" sentence is
  removed. Generated tables are unchanged.
- **Prompt `agent_system_v7`** (the v6 estimate rules plus the skills block) for `agent_skills` and `agent_hybrid_skills`, and
  **`graph_system_v3`** for `agent_graph_skills`, so the skill-using variants no longer describe the r1 estimate.
- **Harness.** `llm-eval` results keep, per skills arm and question, the names of the skills loaded (counts and names only, no tool text),
  so H-S3 can be reported.

## Method and hypotheses (evaluated once, on the 90 November items, after the code is frozen)

One `llm-eval.yml` run on `power-2026-11a.jsonl` with `agent`, `agent_quant` r2 and `agent_skills` r2 on the same items, prompt caching as
in the live setting (off), with the replayed `ml` probabilities passed to every arm. The run is shared with H-Q6 of
`lab/prereg/agent-quant-r2.md`.

- **H-S1'**: `agent_skills` r2 has a lower Brier than `agent_quant` r2 (paired day-block interval entirely below zero).
- **H-S2'**: cost per question asked at most 1.30 times that of `agent_quant` r2 in the same run.
- **H-S3** (descriptive): share of questions that loaded each skill, from the saved traces.

## Decision rule

`agent_skills` r2 goes to a dry run and the owner's decision only if H-S1' and H-S2' both hold; otherwise it stays off and the card says
why. `agent_graph_skills` and `agent_hybrid_skills` have no replay (no LangGraph runtime, no retriever); they launch only after
`agent_skills` passes and are then judged live against their base forecasters. All results are published with intervals, sample sizes
and per-template tables, negative ones included. No change is made because of how the November items resolved (I8). The paid run needs
the owner's OK and lab budget (H46).
