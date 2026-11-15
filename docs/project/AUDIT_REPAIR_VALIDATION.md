# T193 audit repair validation — 2026-11-15

Repair commit: [5cfebf05580056eb9fb92577a1bc695f1614e246](https://github.com/JASHD12/forecast-arena/commit/5cfebf05580056eb9fb92577a1bc695f1614e246).
All nine repair areas in the handoff are implemented. T057/T193e remain waiting for
16 November's first unsealed real morning batch; no historical ML forecasts were added.

## Automated validation

- Local `make check` with coverage: 600 unit tests and 7 E2E tests passed; 89.39% coverage
  against the existing 87% floor. Ruff, formatting, mypy and README badge checks pass.
- `make site-e2e`: site and internal link checks pass. Site built from the real downloaded
  ledger also passes its link check.
- New fresh-process regression tests publish, reload and forecast with actual HGB,
  LightGBM and PyTorch artifacts. Dedicated CI installs base plus inference dependencies
  without training/tracking extras and passes all three families.
- [CI 43737672954](https://github.com/JASHD12/forecast-arena/actions/runs/43737672954):
  every job passed (check, ml-inference, audit, a11y/notebook, Docker/API, dbt, Airflow, kind).
- [Promotion 43738753112](https://github.com/JASHD12/forecast-arena/actions/runs/43738753112)
  passed; both main and stable were verified at the repair commit before live dispatch.

## Live evidence

- Sunday's [weekly run 43695904785](https://github.com/JASHD12/forecast-arena/actions/runs/43695904785)
  had already published real power and attention champions. The repaired loader verified
  their artifact hashes and loaded both locally. Re-training solely for bootstrap was unnecessary.
- [Observer 43739000811](https://github.com/JASHD12/forecast-arena/actions/runs/43739000811)
  passed and appended a complete audit on the observation day. A separate read-only local
  API integration found 17 relevant attempts and correctly rejected historical days missing
  the new execution evidence. The observer also ran automatically after workflow completion.
- Initial [resolve dispatch from stable](https://github.com/JASHD12/forecast-arena/actions/runs/43739003408)
  correctly recorded the missing-ML health failure, but Pages rejected its stable event ref
  under the existing environment branch policy. No environment/settings policy was changed.
- After verifying main and stable had identical tested code,
  [resolve from main 43739259441](https://github.com/JASHD12/forecast-arena/actions/runs/43739259441)
  successfully deployed Pages and passed the published-site smoke test. Its overall workflow
  conclusion remains failure because the application health check now detects the absent
  ML roster in the already sealed 15 November batch. All other recorded checks pass.
- Execution evidence records actual application code SHA 5cfebf0. Health reports include
  workflow/run-attempt identity, and the evening workflow now persists its health output.
- [Ledger snapshot 86d650a](https://github.com/JASHD12/forecast-arena/tree/86d650a)
  verifies with `arena ledger verify --git`: 83 files, 3 batch seals, 3 day seals,
  139 forecasts checked. Added data comprises append-only runs/health/execution/audit
  evidence and legitimately due resolutions. Previously sealed records remain unchanged.

## Next acceptance check

The 15 November batch was sealed before activation with 29 questions and no ML entries.
Do not append late ML forecasts or backdated skips. On the next actual pre-lock morning
batch (16 November), verify:

1. Every expected forecaster/question pair has one forecast or explicit skip; registered
   power/attention champions and weather/markets rule models produce valid ML probabilities.
2. Artifact/version metadata matches the current promoted champions. Disabled crypto stays off.
3. The batch is publicly committed/sealed before its lock and `ledger verify --git` passes.
4. Health and the independent completed-workflow audit report actual outcomes; any real
   failures remain visible. The new complete-evidence gate must not infer old days were clean.
5. After resolution, canonical scores and SQL/API/Parquet/HTML eligibility agree.

The configured morning cron slots are 00:15–08:15 UTC (01:15–09:15 Europe/Berlin in
November); scheduling delay remains possible. The lock is 09:30 UTC (10:30 local).
Manual deploy runs must use the Pages-allowed main event ref only after verifying it
matches the CI-approved stable commit. Keep the owner's official not-before date unchanged.
