# Contributing

Thanks for looking. This repository has two parts with different rules.

## forecast-audit (open to contributions)

`examples/forecast-audit/` is a standalone tool: Python 3.12, standard library only.

```bash
python3 -I examples/forecast-audit/selfcheck.py
make forecast-audit-test
```

Good first contributions: a clearer error message, another invalid-input test, a worked example
from your own domain (binary outcomes and probabilities only, no data you are not allowed to share).

Rules for changes:

- No new dependencies in the tool. It must run on a bare Python 3.12.
- No network access, no secrets.
- Every number in a report is computed by code; add a test with a hand-checked value.
- Behaviour changes need a line in `examples/forecast-audit/SCHEMA.md` and a new schema version.

## Reproducible examples

Found a case where the report looks wrong? Use the
[reproducible example form](.github/ISSUE_TEMPLATE/reproducible-example.yml) with two small CSV
files (a few rows is enough) and the command you ran.

## The forecasting arena itself

The ledger, scoring rules and forecasters follow `AGENTS.md` (append-only ledger, forecast before
truth, no tuning on the live record). Changes there are made by the maintainer's workflow; open an
issue first.

## Conduct

Be kind, be specific, assume good faith. This is a research project, not advice of any kind.
