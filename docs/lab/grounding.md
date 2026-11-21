# Numeric grounding of model rationales

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-grounding.json`, created 2026-11-21T14:53:16Z.

Why companies use it: Checking generated answers against their source data is the cheapest first line of LLM evaluation, before any LLM-as-judge (docs/SOURCES.md, lab sources).

| Variant | Questions | Numbers checked | Numbers not in the prompt % | Rationales with such a number % |
|---|---|---|---|---|
| agent | 80 | 859 | 44.1 | 88.8 |
| agent_graph | 25 | 299 | 56.5 | 100.0 |
| llm_context | 83 | 788 | 41.8 | 75.9 |
| llm_local | 78 | 337 | 20.5 | 52.6 |
| llm_plain | 84 | 301 | 40.5 | 52.4 |


- Every stored live rationale and key factor with a stored morning context (350 rationales; 1008 forecasts in the ledger).
- Trivial numbers (small integers, years, dates) are ignored. A number counts as in the prompt if it equals one in the question, the rule or the context within its rounding or 1%.

## What this does and does not show

- Not in the prompt is an upper bound on invented figures: a model can compute things (a weekly mean of seven values, for example) that are legitimate but not literally in the prompt.
- The agents also read tool results (series, base rates, retrieval) that are not part of the stored morning context, so their share is overstated here.
- It does not judge whether the reasoning is good, only whether the figures it quotes can be traced.
- Small sample: the live record is a few days old; the numbers will move.

Paid-call cost: US$0.00.
