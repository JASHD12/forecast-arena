# Lab budget

Hard limit for all paid lab runs together: **US$3.00** (owner decision 2026-11-28: US$2.50 in the morning for the r2/r3 evaluation, then US$3.00 for Tier C; it was US$2.00 from 2026-11-21). The table is the record; `scripts/lab_budget.py`
sums the `cost_usd` of `evals/results/lab-*.json` and fails `make check` if the total is above the limit or the table is stale.

| Run | Date | Workflow run id | Tokens | US$ | Running total |
|---|---|---|---|---|---|
| lab-judge (first run; no result file: 63 of 100 answers failed the format, output cap 500 was too low, fixed to 1,000) | 2026-11-22 | 45070263620 | 197,531 | 0.04 | 0.04 |
| lab-routing (Claude `llm_context` on 276 test questions) | 2026-11-22 | 45070266130 | 784,145 | 0.15 | 0.19 |
| llm-eval with self-consistency k=5 (24 questions; plain, context, context x5) | 2026-11-22 | 45071241581 | 447,202 | 0.09 | 0.28 |
| lab-distill-labels first run (773 of 1,200 labelled; stopped at its own 2.2M token cap; rows 774 onward still to label) | 2026-11-22 | 45071238970 | 2,197,494 | 0.41 | 0.69 |

| lab-judge (second run, 100 rationales, all scored, no skips) | 2026-11-22 | 45079867618 | 194,536 | 0.04 | 0.73 |
| lab-distill-labels second run (rows 774 to 1,199; 425 labelled, 1 parse error) | 2026-11-22 | 45079870076 | 1,217,859 | 0.23 | 0.96 |
| lab-judge second judge (Claude Sonnet 5.5, the 30 labelled items, 30 of 30 scored; estimate was 0.22) | 2026-11-23 | 45258529928 | 49,479 | 0.13 | 1.09 |
| llm-eval on the 90 November items: agent, agent_quant, agent_skills, agent_committee (one run, all arms answered or skipped by their own rules; estimate was 0.45-0.55) | 2026-11-26 | 45883972017 | 2,956,832 | 0.41 | 1.50 |
| llm-eval, committee r2 only (agent_committee on the 90 November items; the agent_skills arm reused from the first run) | 2026-11-26 | 45905311845 | 1,003,169 | 0.18 | 1.68 |
| llm-eval Tier A: agent_analyst and raw llm_context on the 90 November items (estimate was 0.13) | 2026-11-28 | 46146533142 | 935,475 | 0.13 | 1.81 |
| llm-eval Tier B: raw llm_context on the 186 October items, second test of the calibration map (estimate was 0.09) | 2026-11-28 | 46161529335 | 541,785 | 0.10 | 1.91 |
| llm-eval four arms on the 90 November items: agent, agent_quant r2, agent_skills r2, agent_committee r3 (token cap 3.5M used up during the committee arm: 12 questions skipped by the cap; estimate was 0.45) | 2026-11-28 | 46162162189 | 3,500,064 | 0.49 | 2.40 |
