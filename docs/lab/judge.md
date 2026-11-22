# LLM-as-judge for stored rationales

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-judge.json`, created 2026-11-22T23:04:14Z.

Why companies use it: A rubric-based LLM grader, calibrated against a small human-labelled set, is the standard way teams evaluate open-ended LLM output at scale.

| Variant | Questions |
|---|---|
| judge / agent | 20 |
| judge / agent_graph | 20 |
| judge / llm_context | 20 |
| judge / llm_local | 20 |
| judge / llm_plain | 20 |


- 100 of 100 rationales were graded.

## What this does and does not show

- The judge model is the same family as the forecasters it grades, so it may favour their style.
- At most 30 human labels: the agreement estimate is rough.
- It grades the stated reasoning, not whether the forecast turned out right.

Paid-call cost: US$0.04.
