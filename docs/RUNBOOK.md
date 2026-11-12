# RUNBOOK.md - operating Forecast Arena

How the live system runs every day, and what to do when it does not.

## Daily operations

Everything runs on GitHub Actions from the `stable` branch (the last commit of `main`
that passed CI; `promote.yml` fast-forwards it after every green CI run). All ledger
writers share the concurrency group `arena-ledger`, so two jobs never push at once.

| Time (UTC) | Workflow | What it does |
|---|---|---|
| 05:30, 07:00 | `morning.yml` | Generates the day's questions, runs every forecaster, snapshots the inputs, seals the batch, pushes the `ledger` branch, verifies it, rebuilds and deploys the site. The second run is a no-op if the first succeeded. |
| 09:30 | (lock) | Every question of the day locks. A run after this writes nothing ("late run" in its manifest). |
| 12:30, 16:30, 20:30, 03:30 | `resolve.yml` | Resolves whatever has become resolvable, records source revisions, seals finished days, verifies, rebuilds and deploys the site. |
| Sunday 02:00 | `weekly.yml` | Retrains models, promotes them only by the rule in `src/arena/ops/weekly.py`, writes a summary and drift metrics to the ledger. |
| 1st of the month 06:17 | `deps.yml` | Lists outdated dependency pins in the run summary. |

What to look at (a few minutes):

1. The site's **Home** page: today's batch is there, and "ledger verification" says PASS.
2. The **Status** page: latest runs `ok`; no growing count of voids or skips.
3. The repository's **Actions** tab: the last morning and resolve runs are green.
4. Open issues labelled `incident` (once health checks are live, T033).

Manual runs (standing approval 6): Actions tab > workflow > Run workflow. Keep
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
| A morning run says "late run" | The scheduled run started after 09:30 UTC | Nothing to repair: the day has no forecasts and that is recorded. Check whether GitHub's schedule is delayed; the 05:30 and 07:00 runs exist for this. |
| Morning run fails in question generation for one domain | A source was down or returned malformed data | The other domains still run. Check the source with `make smoke-sources`. The run manifest on the ledger lists the warning. |
| Push to `ledger` rejected | Another job pushed first | The job pulls with rebase and retries up to five times; if it still fails, re-run the workflow (it is idempotent). |
| `ledger verify` fails | A sealed file changed or a forecast is after its lock | Stop: this is an integrity incident. Do not "fix" the ledger. Open an issue, compare with an older clone, and investigate the commit history. |
| Site not updated | The Pages deploy job failed | Re-run the workflow; Settings > Pages must have source "GitHub Actions". |
| `promote` fails ("not an ancestor") | `stable` diverged from `main` | Investigate; never force-push `stable`. |
| LLM forecasters show `budget_exhausted` | The daily caps were reached | Expected behaviour (SPEC 9.4). Raise caps only deliberately, via Actions variables. |
| LLM forecasters show `model_missing` | No key or model configured | H04 in HUMAN_TODO.md. |
