# Lab budget

Hard limit for all paid lab runs together: **US$2.00** (owner decision 2026-11-21). The table is the record; `scripts/lab_budget.py`
sums the `cost_usd` of `evals/results/lab-*.json` and fails `make check` if the total is above the limit or the table is stale.

| Run | Date | Workflow run id | Tokens | US$ | Running total |
|---|---|---|---|---|---|
| lab-judge (first run; no result file: 63 of 100 answers failed the format, output cap 500 was too low, fixed to 1,000) | 2026-11-22 | 45070263620 | 197,531 | 0.04 | 0.04 |
| lab-routing (Claude `llm_context` on 276 test questions) | 2026-11-22 | 45070266130 | 784,145 | 0.15 | 0.19 |
| llm-eval with self-consistency k=5 (24 questions; plain, context, context x5) | 2026-11-22 | 45071241581 | 447,202 | 0.09 | 0.28 |
| lab-distill-labels first run (773 of 1,200 labelled; stopped at its own 2.2M token cap; rows 774 onward still to label) | 2026-11-22 | 45071238970 | 2,197,494 | 0.41 | 0.69 |

