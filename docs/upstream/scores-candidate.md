# Upstream candidate: `scores` (note for the owner; nothing is posted)

`scores` is an open-source Python package for verification of forecasts. A possible contribution is
a documented, tested example for **common-case selection**: computing a Brier score only on cases
where every compared model issued an on-time forecast.

## Steps if you decide to go ahead (owner only; the agent opens no issue or pull request)
1. Read the project's contributing guide and licence; check whether the example already exists.
2. Reproduce the four-case fixture of `examples/forecast-audit/` with `scores` (raw Brier on the
   three on-time cases: 0.213333 versus 0.28 for the reference).
3. Open an issue describing the use case before any code.

## Honest note
This repository's tool is independent and standard-library only; an upstream example would not
replace it.
