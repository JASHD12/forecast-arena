# Lab budget

Hard limit for all paid lab runs together: **US$2.00** (owner decision 2026-11-21). The table is the record; `scripts/lab_budget.py`
sums the `cost_usd` of `evals/results/lab-*.json` and fails `make check` if the total is above the limit or the table is stale.

| Run | Date | Workflow run id | Tokens | US$ | Running total |
|---|---|---|---|---|---|
| lab-judge (first run; no result file: 63 of 100 answers failed the format, output cap 500 was too low, fixed to 1,000) | 2026-11-22 | 45070263620 | 197,531 | 0.04 | 0.04 |
