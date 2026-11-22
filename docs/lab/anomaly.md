# Unsupervised data-anomaly detection on price windows (Isolation Forest)

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-anomaly.json`, created 2026-11-22T10:25:21Z.

Why companies use it: Label-free anomaly detection on incoming data is how production ML teams catch broken feeds before a model silently uses them.

| Variant | Questions |
|---|---|
| isolation_forest | 122 |
| robust_z | 122 |


- 122 real 28-day windows from 2025-11-01 to 2026-10-31 (every third day); thresholds from clean windows of 2019-01-01 to 2024-12-31 for about 5% false alarms: {k: round(v, 3) for k, v in res['threshold'].items()}.
- Faults are injected into the latest day only: a spike (one hour times 8), a unit error (prices divided by 1000), a flat feed and a repeated day.

## What this does and does not show

- Injected faults are synthetic; real feed failures can look different.
- A window of 28 days is short; a repeated day is hard for any detector that only looks at daily statistics.

Paid-call cost: US$0.00.
