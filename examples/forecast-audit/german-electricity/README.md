# German electricity example: would the extra model have changed any alert?

A replayed decision study over **46 evening-price questions** (target days 2 Oct - 16 Nov 2026, batch days
1 Oct - 15 Nov 2026) for the German/Luxembourg day-ahead market. The event: *the mean of the three hourly
prices 17:00-20:00 Berlin time on the target day is above that question's published price threshold.*
Under an **illustrative** cost of 1 for an unnecessary alert and 4 for a missed event, an operator alerts when
the forecast probability is at least 0.20.

Run it (offline, standard library only):

```sh
python3 examples/forecast-audit/report.py --cases examples/forecast-audit/german-electricity/cases.csv \
  --predictions examples/forecast-audit/german-electricity/predictions.csv \
  --candidate fine_tuned_gguf --baseline base_rate --timing-label replayed \
  --false-alert-cost 1 --miss-cost 4 --out report/
```

`expected/` holds the report this produces (the test suite checks it, and a DuckDB query in `audit.sql`
computes the same counts and losses independently).

| What | Value |
|---|---|
| Cases, YES / NO | 46, 29 / 17 |
| Base rate: Brier, alerts, false alerts, misses, loss | 0.2337, 46, 17, 0, 17 |
| Fine-tuned GGUF model: Brier, alerts, false alerts, misses, loss | 0.2499, 46, 17, 0, 17 |
| Always alert / never alert: loss | 17 / 116 |

**The base rate has the better probability score, and both make exactly the same 46 decisions** (every probability
is above 0.20). Under these costs the extra model changes nothing. With a 1:1 cost ratio (cutoff 0.50) the
model alerts less often and its loss is *higher* than always alerting; the sensitivity tables in the report
show it.

**What this cannot show.** The costs are assumed, not an operator's. These are replayed cases that were
studied before: the numbers are neither a forecast of future performance nor real savings. The timing is a
**replay** (probabilities are stamped with the as-of time recorded in the frozen set), not a ledger-verified
live time. The classical gradient-boosted model is not in this comparison because the row-level predictions of
its original backtest were not kept; it can be added from a separately identified replay.

Files: `build_case.py` (rebuilds the CSVs from the repository's frozen records; `--check` verifies them),
`MANIFEST.json` (sources, hashes, transformations, terms), `DATA_LICENSE.md`, `audit.sql`.
