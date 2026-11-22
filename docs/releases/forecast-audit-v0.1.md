# forecast-audit v0.1 (release candidate)

Status: candidate. Tagging and publishing are the owner's step.

## What it is

An offline tool (Python 3.12, standard library only) that audits alert decisions from forecast
probabilities against a baseline, from two CSV files.

## Included

- `examples/forecast-audit/forecast_audit.py` and `report.py` (CLI), `selfcheck.py`
- `SCHEMA.md` (schema version 1), four-case golden fixture
- German electricity example: 46 replayed evening-price cases, manifest, expected outputs,
  DuckDB cross-check (`audit.sql`)
- CI job on a bare Python 3.12

## Known limits

- The electricity example is a replay of frozen records (label `replayed`), not a live result.
- It compares two models, not a classical gradient-boosted arm (its row-level predictions were
  never committed).
- Costs are illustrative units, not money.
- Not investment or operational advice.

## Changelog

- 0.1.0: first release candidate.
