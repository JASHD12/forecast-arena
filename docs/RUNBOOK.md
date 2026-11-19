# RUNBOOK.md - operating Forecast Arena

How the live system runs every day, and what to do when it does not.

## Daily operations

Everything runs on GitHub Actions from the `stable` branch (the last commit of `main`
that passed CI; `promote.yml` fast-forwards it after every green CI run). All ledger
writers share the concurrency group `arena-ledger`, so two jobs never push at once.

| Cron slots (UTC) | Workflow | What it does |
|---|---|---|
| hourly 00:15 to 08:15 | `morning.yml` | A `gate` job asks `arena schedule due --job morning` whether the batch is still unsealed and before the lock; only then does the run generate any missing questions, run every forecaster, snapshot the inputs, seal the batch, push the `ledger` branch, verify it, and rebuild and deploy the site. Later slots are no-ops. |
| 09:30 | (lock) | Every question of the day locks. A run after this writes nothing ("late run" in its manifest). |
| hourly 16:00 to 23:00 | `evening.yml` | Publishes tomorrow's questions (template v2) once, via the same gate. |
| 08:40, 09:00, 09:15 | `players.yml` | Writes the public players' forecasts shortly before the lock (needs H15). |
| every 3 hours at :30 | `resolve.yml` | Resolves whatever has become resolvable, records source revisions, seals finished days, verifies, rebuilds and deploys the site. |
| Sunday 02:00 | `weekly.yml` | Retrains models, promotes them only by the rule in `src/arena/ops/weekly.py`, writes a summary and drift metrics to the ledger. |
| 1st of the month 06:17 | `deps.yml` | Lists outdated dependency pins in the run summary. |

**GitHub starts scheduled runs late.** On this repository the 00:15 morning slot has
started between about 06:20 and 07:53 UTC, evening runs between 22:52 and 04:00, and
players runs between 17:31 and 19:37 (after the lock, so intake cannot work from the
cron alone). That is why the jobs are scheduled hourly behind a gate. The Status page shows
when scheduled jobs actually started. The fix that does not depend on GitHub's scheduler
is owner item H20 (an external scheduler that calls `workflow_dispatch`, see
`docs/project/HUMAN_TODO.md`). A dispatch is always "due", but a morning run after the seal
does nothing (`tests/unit/test_jobs.py::test_morning_writes_seals_and_is_idempotent`), so
extra dispatches are safe.

SMARD forecast timing (T222b): the morning and evening run summaries contain `smard-forecast` lines
(when SMARD rewrote its forecast chunk and whether tomorrow is covered). It is a measurement only.

What to look at (a few minutes):

1. The site's **Home** page: today's batch is there, and "ledger verification" says PASS.
2. The **Status** page: latest runs `ok`; no growing count of voids or skips.
3. The repository's **Actions** tab: the last morning and resolve runs are green.
4. Open issues labelled `incident`. After every morning, resolve and real weekly run, the
   health checks (`arena health check`: batch sealed before lock, nothing overdue, sources
   fresh, LLM parse failures under 20%, ledger verify) run; a failed job or check opens one
   issue titled "Forecast Arena incident: a job or health check failed" (or comments on
   the open one), and the next healthy run closes it. The run summary shows the table.

Manual runs (standing approval 6): Actions tab > workflow > Run workflow, **from `main`**
(the `github-pages` environment only accepts deployments from `main`; a run started from
`stable` fails in its deploy job; scheduled runs are fine because they start on `main` and
check out `stable`'s code). Keep
`dry_run` ticked to test without writing anything; untick it only for a deliberate real
run (a real morning run after 09:30 UTC is refused by the job itself and writes nothing).

Checking the record yourself:

```bash
git clone --branch ledger --single-branch https://github.com/JASHD12/forecast-arena.git _ledger
```

```bash
.venv/bin/arena --ledger-dir _ledger ledger verify --git
```

## If something breaks

Never edit or rewrite the `ledger` branch, never force-push, never backdate a forecast
(AGENTS.md I1, I2). Fixes are code changes on `main` (which reach `stable` after CI) or
new correcting records.

| Symptom | Likely cause | What to do |
|---|---|---|
| Jobs fail within seconds, no steps run | Account billing lock or an Actions budget of $0 (seen on 2026-11-12) | github.com/settings/billing: fix the payment issue; raise the Actions budget above $0. Re-run. |
| No morning run by 08:00 UTC (GitHub skipped both schedules, seen on 2026-11-13) | GitHub drops scheduled runs under load | Start it by hand before 09:30 UTC: Actions > morning > Run workflow from `stable` (tested code; its Pages deploy step fails by design) or from `main` if `main` == `stable`. The site updates at the next resolve run. |
| Status page: "rehearsal: n clean day(s) in a row" stays low | A day had no successful morning run, a failed run, a failed health check, or is not sealed yet | The Status page lists the reason per day. Fix the cause; the streak restarts. The official record also waits for the not-before date (`ARENA_OFFICIAL_START_NOT_BEFORE`, default 2099-12-31 until the roadmap changes are live). |
| A morning run says "late run" | The scheduled run started after 09:30 UTC | Nothing to repair: the day has no forecasts and that is recorded. Check whether GitHub's schedule is delayed; the 05:30 and 07:00 runs exist for this. |
| Morning run fails in question generation for one domain | A source was down or returned malformed data | The other domains still run. Check the source with `make smoke-sources`. The run manifest on the ledger lists the warning. |
| Push to `ledger` rejected | Another job pushed first | The job pulls with rebase and retries up to five times; if it still fails, re-run the workflow (it is idempotent). |
| `ledger verify` fails | A sealed file changed or a forecast is after its lock | Stop: this is an integrity incident. Do not "fix" the ledger. Open an issue, compare with an older clone, and investigate the commit history. |
| Site not updated | The Pages deploy job failed | Re-run the workflow from `main`; Settings > Pages must have source "GitHub Actions". "Branch ... is not allowed to deploy to github-pages" means it was started from another branch. |
| `promote` fails ("not an ancestor") | `stable` diverged from `main` | Investigate; never force-push `stable`. |
| LLM forecasters show `budget_exhausted` | The daily caps were reached (150000 tokens/day in the workflows: the owner's ~$1/month ceiling) | Expected behaviour (SPEC 9.4). Raise caps only deliberately, via Actions variables, and only with the owner's agreement on cost. |
| LLM forecasters show `model_missing` | No key or model configured | H04 in docs/project/HUMAN_TODO.md. |
