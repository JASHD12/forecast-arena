# forecast-audit

A small offline tool for one question: *if I send alerts from my model's probabilities, do
decisions improve over a baseline, including the days the model misses?*

Python 3.12, standard library only. No network, no keys, no install.

## Quickstart

```bash
python3 -I examples/forecast-audit/report.py \
  --cases examples/forecast-audit/cases.csv \
  --predictions examples/forecast-audit/predictions.csv \
  --candidate demo --baseline reference \
  --false-alert-cost 1 --miss-cost 4 --on-missing no-alert --out build/audit
```

This writes `report.json`, `cases-audited.csv` and `report.html` into `build/audit`.
`make forecast-audit-demo` runs this and the German electricity case.

## Inputs

Two CSV files; the contract is in [SCHEMA.md](SCHEMA.md).

- `cases.csv`: `case_id, group_day, lock_at, outcome_state, outcome`
- `predictions.csv`: `case_id, model_id, status, probability, issued_at, reason`

A forecast counts as on time only if `issued_at` is strictly before `lock_at`. Invalid input
exits with code 2 and writes nothing.

## What it reports

1. Timeliness and coverage (on time, late, skipped, absent).
2. Probability quality (Brier, raw and clipped to [0.01, 0.99]) on identical on-time resolved cases.
3. Decision performance: alert if `p >= false_alert_cost / (false_alert_cost + miss_cost)`, loss per
   policy, with 1:1 and 1:9 cost ratios as sensitivity.

Timing is labelled `declared`, `replayed` or `ledger-verified`; the tool never upgrades a label.

## Examples

- Four-case golden fixture (this folder).
- [German electricity case](german-electricity/README.md): 46 historical evening-price cases, a replay.

## Checks

```bash
python3 -I examples/forecast-audit/selfcheck.py
make forecast-audit-test
```

Code is MIT (repository `LICENSE`). Data files carry their own terms: see
[german-electricity/DATA_LICENSE.md](german-electricity/DATA_LICENSE.md).
