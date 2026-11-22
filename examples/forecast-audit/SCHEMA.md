# Forecast audit: input and output contract (schema version 1)

Standard library only, Python 3.12. No network, no keys, no packages. Private files stay on your machine.

```sh
python3 examples/forecast-audit/report.py --cases examples/forecast-audit/cases.csv \
  --predictions examples/forecast-audit/predictions.csv --candidate demo \
  --baseline reference --false-alert-cost 1 --miss-cost 4 --on-missing no-alert --out report/
```

Exit code 0: the report was written. Exit code 2: the input is invalid; every problem is printed as
`error: <file> row <n>: field <name> ...` and **nothing is written**.

## `cases.csv`: one row per *expected* case (include cases nobody predicted)

| column | meaning |
|---|---|
| `case_id` | unique text id |
| `group_day` | `YYYY-MM-DD`, the event day (cases of one day are summed for the daily loss) |
| `lock_at` | ISO 8601 time **with a UTC offset**; a prediction must be issued strictly before it |
| `outcome_state` | `resolved`, `pending` (label not known yet) or `void` (cancelled; never scored) |
| `outcome` | `0` or `1` when resolved, empty otherwise |

## `predictions.csv`: one row per (case, model) that has any submission

| column | meaning |
|---|---|
| `case_id`, `model_id` | the pair is unique; `case_id` must exist in `cases.csv` |
| `status` | `forecast` or `skipped` (an intentional, explained skip) |
| `probability` | finite number in [0, 1] when `status` is `forecast` |
| `issued_at` | ISO 8601 time with a UTC offset (required for a forecast) |
| `reason` | required for `skipped`, optional otherwise |

A (case, model) with no row is **absent**. Each pair ends up in exactly one state: `on_time`
(`issued_at` strictly before `lock_at`; equality is late), `late`, `skipped` or `absent`.

## Rules

- **Quality** (Brier): compared only on identical cases that are resolved and on time for **both** the
  candidate and the baseline. Raw Brier and Brier with probabilities clipped to [0.01, 0.99] (the Arena
  convention; a certain correct answer scores 0 raw and 0.0001 clipped). Undefined on an empty shared set.
- **Decision**: alert when `p >= false_alert_cost / (false_alert_cost + miss_cost)`; ties alert. An
  unnecessary alert costs `false_alert_cost`, a missed event `miss_cost`, correct actions 0. Loss is
  computed over **all resolved cases**; a late, skipped or absent prediction uses `--on-missing`
  (`no-alert`, `alert`, or `baseline` = the baseline's action when it was on time, else no alert) and the
  number of fallbacks is reported. `always_alert` and `never_alert` are always shown, and a sensitivity
  table at miss-to-false-alert ratios 1 and 9 next to your primary ratio.
- **Per case and per day** are separate named metrics (`loss_per_case`, `mean_daily_total_loss`).
- **Interval**: a seeded bootstrap of the mean daily loss difference (candidate minus baseline), resampling
  days (and moving 7-day blocks when there are at least 60 days). With fewer than 30 resolved days it says
  "not estimated" and why. Days are serially correlated; the interval is a description, not a guarantee.
- **Timing label** (`--timing-label`): `declared` (times as supplied: a file cannot prove its own
  publication time), `replayed` (a historical replay) or `ledger-verified` (checked against a sealed
  public history; only claim it after doing that check).
- **Roster** (`--roster unknown`): if the list of expected cases is not available, coverage is reported
  as unknown and absent counts are not given.

## Outputs (`--out DIR`)

- `report.json`: `schema_version`, `tool_version`, input SHA-256s, time scope, models, rule (cutoff, ties,
  fallback, clipping), units, coverage per model, quality, decision, sensitivity, intervals.
- `cases-audited.csv`: one row per (case, model) with the state, whether it entered quality and decision,
  and the reason it did or did not.
- `report.html`: a static page with accessible tables. Text from your files is escaped.
