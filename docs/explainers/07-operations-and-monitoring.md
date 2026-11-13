# 07 - Operations and monitoring

How Forecast Arena runs every day without anyone watching it, how it notices when
something goes wrong, and how it keeps cost and model changes under control.
Code: `.github/workflows/`, `src/arena/ops/` (`jobs.py`, `health.py`, `official.py`,
`weekly.py`, `drift.py`), `src/arena/llm/budget.py`, `src/arena/site/ops_status.py`,
`docs/RUNBOOK.md`.

## How it works

1. **Schedules on GitHub Actions** (all UTC):
   - `morning` at 05:30, with a second chance at 07:00, because scheduled workflows can
     start late or be skipped;
   - `resolve` at 12:30, 16:30, 20:30 and 03:30;
   - `weekly` on Sunday 02:00;
   - `deps` on the 1st of each month, a report of outdated pins only.
2. **Code promotion.** Every push to `main` runs CI (ruff, mypy, unit tests with coverage,
   offline end-to-end run). If CI passes, the `promote` workflow fast-forwards the
   `stable` branch to that commit and never forces. Scheduled jobs run code from
   `stable`, so a broken commit on `main` cannot break the live record.
3. **One writer at a time.** Morning, resolve and weekly share the concurrency group
   `arena-ledger` without cancellation, so two jobs never write the ledger at once. Ledger
   pushes retry with `pull --rebase` up to five times and never force-push.
4. **Idempotent jobs.** A sealed batch makes later morning runs a no-op; resolutions and
   voids are appended once per question; a rerun of any job for the same date changes
   nothing. That is what makes the 07:00 safety net and manual reruns safe.
5. **Run manifests.** Each job writes `runs/...` with status, counts, warnings, LLM usage
   and the code commit, even when the job fails (the manifest is written in a `finally`
   path).
6. **Health checks after every job** (`arena health check`), each pass or fail:
   - `batch_sealed`: today's batch was sealed before the lock;
   - `nothing_overdue`: no question is unresolved more than 5 days past its answer time;
   - `sources_fresh`: every active domain asked questions within 36 hours (96 for
     markets);
   - `parse_failures`: under 20% of today's LLM answers broke the output contract;
   - `ledger_verify`: the full verification passes.
   On real runs the report is written to `health/...` in the ledger and sealed with the
   day.
7. **Incidents.** A failed job or check opens one GitHub issue labelled `incident`, or
   comments on the open one (deduplicated by title). A healthy run closes it. The owner
   gets GitHub's normal notification, so nobody has to watch dashboards.
8. **Cost control.** Every LLM call goes through `GuardedLLM`. Before a call, the
   `BudgetGuard` adds up today's usage from all run manifests plus this run, and refuses
   when one more call could pass the daily caps (150,000 tokens and 100 requests in the
   workflows; output capped per call). A refused call is recorded as a
   `budget_exhausted` skip, never a guessed probability. Tests and local runs use
   `FakeLLM`; real calls happen only inside Actions.
9. **Weekly retraining with a written rule.** The weekly job trains every candidate model
   family with a cut-off before a 28-day evaluation window and scores it on the window's
   real questions. It promotes the best candidate only if it is not worse than the
   current model. MLflow logs the runs; Evidently compares this window's features and
   predictions with the year before (drift). Permutation importance, SHAP and
   conformal coverage go into the weekly summary in the ledger and onto the Experiments
   page.
10. **The Status page** is rebuilt from the ledger after every job. It shows:
   - the latest runs;
   - missed days and source freshness (latest batch, latest answer, overdue questions);
   - skips and voids by reason;
   - LLM usage per day against the cap, and the LLM parse-failure rate;
   - the clean-day streak towards the official start.

## Why it was built this way

- **No servers.** GitHub Actions and Pages are free for a public repository and need no
  accounts beyond GitHub. A scheduler on a VM would cost money and need patching.
- **`main` vs `stable`.** Developing on the same branch the scheduler runs is the classic
  way to break production at 05:29. Promotion after green CI gives a rollback point for
  free.
- **Alert by issue, not by dashboard.** A human looks in about once a day. An issue is
  durable, notifies by email and keeps the discussion attached to the incident.
- **Health checks are written into the ledger** so the official-start decision ("five
  clean days") can be audited from the public data, not from my word.
- **Caps enforced before the call**, from usage the provider reports, because a cost
  overrun cannot be undone afterwards.

## What was rejected

- Airflow or another hosted orchestrator for production (cost and operations work for a
  handful of daily jobs).
- Retrying a failed forecaster later in the day. The batch is sealed once, and a later
  retry would be a different information set.
- Auto-merging dependency upgrades (the `deps` job only reports).
- Paging or chat alerts (extra accounts and secrets for a once-a-day project).

## Things that actually went wrong

- **2026-11-13: GitHub skipped both morning schedules.** No batch would have been sealed.
  A manual dispatch before the lock saved the day, and the RUNBOOK now describes the
  check-and-dispatch steps. This is the reason for the clean-day rule.
- **Live agent errors ("thinking blocks cannot be modified").** The repair path sent the
  assistant turn twice. It was fixed with a regression test that fails without the fix.
- **Thinking tokens used up the output cap.** Effort now defaults to `low` in the
  workflows, so answers fit in the per-call budget.
- **A health step hid its exit code behind `tee`.** Fixed with `set -o pipefail`. An
  incident was then opened and closed live to prove the alert path (dry runs).

## Ten interview questions

1. **How do you know it ran today?**
   Each job writes a run manifest and a health report to the ledger. The `batch_sealed`
   check fails if no sealed batch exists after the lock, and that opens an `incident`
   issue. The Status page lists missed days.
2. **What happens if GitHub skips a scheduled run?**
   There is a second morning schedule at 07:00. If both are skipped, the owner can
   dispatch the workflow before 09:30 UTC. After the lock nothing can be added. The day is
   recorded as missed, never backfilled.
3. **How do you avoid breaking production with a bad commit?**
   Scheduled jobs run from `stable`. That branch moves only by fast-forward, and only
   after CI passed on that exact commit.
4. **How do you keep LLM costs bounded?**
   A guard sums today's provider-reported usage from the ledger. It refuses any call that
   could pass the daily token or request caps, and the refusal becomes a recorded skip.
   The caps are set in the workflow environment, and the Status page shows usage against
   the cap.
5. **Why are jobs idempotent, and how do you test that?**
   Retries and duplicate schedules are normal on Actions. The end-to-end test runs the
   whole schedule twice into two ledgers and asserts the same files with the same bytes
   (run manifests, which carry run times, are excluded).
6. **How do you detect model drift?**
   Weekly, Evidently compares the evaluation window's features and predictions with the
   year before. The weekly Brier scores form a performance-over-time series. A drop does
   not change the live model by itself: promotion follows the written rule.
7. **What stops you from tuning the model on the live results?**
   The promotion rule is fixed in code and documented. Every model or prompt change gets
   a new version visible on the site, and changes are judged on backtests and held-out
   windows, not on how one live question resolved (integrity rule I8).
8. **What is your alerting strategy?**
   One GitHub issue labelled `incident`, opened on the first failure, commented on after
   that, and closed by the next healthy run. It is low noise, durable, and gives email
   notifications without extra services.
9. **How would you run this at larger scale?**
   The same jobs would run in containers on a scheduler such as Kubernetes CronJobs or
   Airflow. The ledger would move to object storage with the same append-and-seal rules,
   and the health checks would feed a metrics system. The job logic would not change:
   each job is already a single idempotent CLI command.
10. **What is the weakest part of the operations?**
   Dependence on GitHub's scheduler, which has skipped runs, and on single data sources
   per domain. Both are visible on the Status page, and neither can silently corrupt the
   record: the worst case is a missed or voided day.
