# Conformal price bands: coverage by month

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-conformal.json`, created 2026-11-21T20:11:19Z.

Why companies use it: Calibrated uncertainty intervals are what planning teams ask of a forecasting model.

| Variant | Questions | Months | 80% band, raw | 80% band, conformal | 90% band, raw | 90% band, conformal |
|---|---|---|---|---|---|---|
| mean | 214 | 7 | 0.71 | 0.794 | 0.804 | 0.925 |
| max | 214 | 7 | 0.766 | 0.799 | 0.893 | 0.907 |
| min | 214 | 7 | 0.64 | 0.761 | 0.762 | 0.907 |
| spread | 214 | 7 | 0.715 | 0.832 | 0.822 | 0.911 |
| evening | 214 | 7 | 0.696 | 0.822 | 0.869 | 0.911 |


- 35 month-statistic rows from 2026-04-01 to 2026-10-31; targets 80% and 90%.
- Each month: model trained before a 30-day calibration window, CQR margin fitted on that window, bands scored on the month.

## What this does and does not show

- Seven months only; coverage in one month moves with the market regime.
- Conformal guarantees assume exchangeable days, which price series are not.
- Backtest of the production recipe on replayed days; not a live score.

Paid-call cost: US$0.00.
