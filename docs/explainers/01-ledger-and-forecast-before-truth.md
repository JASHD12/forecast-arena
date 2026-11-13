# 01 - The ledger and "forecast before truth"

How Forecast Arena makes its record trustworthy: every question and forecast is written,
sealed and published before the answer exists, and nothing written can be changed later
without that being visible.
Code: `src/arena/ledger/` (`store.py`, `layout.py`, `seal.py`, `verify.py`,
`gitcheck.py`, `gitsync.py`, `manifest.py`), the morning job in `src/arena/ops/jobs.py`.

## How it works

1. **Where it lives.** The ledger is a folder of JSON Lines files on a separate git branch,
   `ledger`, in the public repository. GitHub Actions clones it into `_ledger/`, appends,
   commits (`ledger: <job> <date>`) and pushes. The code that writes it lives on `main`;
   the data never mixes with the code history.
2. **Layout by day.** `layout.py` fixes one path per record family and batch day:
   `questions/YYYY/MM/DD.jsonl`, `forecasts/...`, `resolutions/...`, `runs/...`,
   `health/...`, plus `seals/`. Every path maps back to exactly one day (`day_of`), which
   is what makes per-day sealing possible.
3. **Append-only storage.** `Ledger.append` reads the file, adds the new records, writes
   to a temporary file, validates it (every line parses, ids are unique) and renames it
   atomically. A crash leaves either the old or the new file, never half of one.
   `write_raw` (for one-off files like seals and `meta/official_start.json`) refuses to
   overwrite. There is no update or delete function at all.
4. **Canonical JSON.** Records are pydantic models serialised with sorted keys and fixed
   formatting (`canonical_json`), so the same record always produces the same bytes. That
   is required for hashing: a hash over non-canonical JSON would change when nothing did.
5. **Lock time.** Each question carries a `lock_time` (09:30 UTC on the batch day B). The
   morning job refuses to run for a date other than today's UTC date, refuses to start
   at or after the lock, and re-checks the clock after generating questions; if the lock
   passed meanwhile it writes nothing and records a "late run". Every forecast stores its
   `created_at`, and `verify` fails any forecast created at or after its question's lock.
6. **Batch seal.** Right after the forecasts are written, `seal_batch` writes
   `seals/batch/YYYY-MM-DD.json` with the SHA-256 of every question and forecast file of
   the batch. Once sealed, later morning runs that day do nothing.
7. **Day seal and hash chain.** After the day's resolutions, `seal_day` hashes every file
   of the day and chains it to the previous day:
   `chain = sha256(prev_chain + "\n" + sorted("path:sha256" lines) + "\n")`, starting from
   64 zeros. Changing any byte of any earlier day changes its hash, which breaks every
   later chain value.
8. **Verification.** `arena ledger verify` recomputes every file hash, batch seal, day
   seal and the chain, checks that every record parses and is canonical, that ids are
   unique, and that every forecast is before its lock. `--git` additionally reads the
   branch history and checks that each batch's commit landed before its lock time. Anyone
   can run both on a fresh clone; the Guide page shows the commands.
9. **Run manifests and health reports.** Each job writes a manifest (`runs/...`: job,
   status, counts, warnings, dry-run flag) and a health report (`health/...`), both sealed
   with the day. The official start of the record is decided from these files alone
   (`src/arena/ops/official.py`): five clean days in a row, written once.
10. **Corrections.** A wrong record is never edited. A correction is a new record that
   says what it corrects (for example a `source_revised` void when the data source
   revises a value after resolution; scores keep the first resolution).

## Why it was built this way

- **Pre-registration is the whole point.** A forecasting benchmark is only credible if
  forecasts provably existed before the outcome. Locks, seals and public commits are three
  independent pieces of evidence for that.
- **Git as the transport.** It is free, every clone keeps the full history, and GitHub
  shows push times. A database would need hosting and would be easier to edit silently.
- **Hash chain, not blockchain.** The threat is a quiet edit by the operator, not an
  untrusted network. A chain over daily hashes plus public history detects that; consensus
  protocols would add cost and nothing useful.
- **Recompute scores, do not store them.** The ledger stores facts (questions, forecasts,
  outcomes). Scores are a pure function of facts, recomputed on every site build, so a
  scoring bug can be fixed without touching the record.
- **Atomic writes and idempotent jobs.** Actions runners can be killed at any moment and
  scheduled runs are sometimes skipped or doubled. Running a job twice must change nothing
  the second time.

## What was rejected

- A hosted database (cost, and no public audit trail).
- Editing or deleting bad records (breaks trust; corrections are new records instead).
- Timestamping services or signing keys (extra accounts and secrets; git history plus the
  chain were judged enough for this threat model, and the limits are stated openly).
- Backfilling a missed day "as if" forecast in the morning (forbidden by integrity rule
  I1; a missed batch is recorded as missed).

## Honest limits

- Git committer dates are set by the committer. The `--git` check is evidence, not proof;
  the GitHub Actions logs and the push events on GitHub's side are the stronger evidence.
- The operator could in principle force-push a rewritten branch. Every existing clone
  would then disagree with the new history, which is why the repository is public and why
  force-pushing is banned in the operating rules.
- The hash chain proves files were not changed after sealing, not that the data source
  was right.

## Ten interview questions

1. **How do you prove a forecast was made before the answer was known?**
   Three things: the forecast's `created_at` must be before the question's lock (checked
   by `verify`), the batch is sealed with file hashes right after writing, and the git
   commit is pushed to a public branch before the lock (checked by `verify --git`). The
   answers for power questions are only published hours after the lock.
2. **What stops you from editing yesterday's forecasts?**
   The day seal stores the hash of every file, and each day's chain hash includes the
   previous one. Editing one byte breaks `verify` for that day and all later days. The
   branch is public, so a rewritten history would contradict every existing clone.
3. **Why JSON Lines files on a git branch instead of a database?**
   Free hosting, a built-in public audit trail, easy diffing, and anyone can verify with
   `git clone`. The volume (tens of records per day) is tiny. For analysis the site
   exports Parquet and the Data page queries it with DuckDB.
4. **What happens if a job crashes halfway?**
   Every write goes to a temp file that is validated and then renamed atomically, so no
   partial file exists. Jobs are idempotent: rerunning skips what is already written. The
   run manifest records the failure, and the health check opens an `incident` issue.
5. **What if the morning job runs late?**
   It refuses to write anything at or after 09:30 UTC and records a late run. There is no
   backfill. This happened on 2026-11-13, when GitHub skipped the scheduled runs; a manual
   run before the lock saved the batch, and the RUNBOOK now covers it.
6. **Why canonical JSON?**
   Hashes are over bytes. Without one fixed serialisation, re-saving the same record with
   different key order would change its hash and look like tampering.
7. **How do you correct a mistake?**
   With a new record that names what it corrects, never by editing. For example, if SMARD
   revises a price after resolution, a `source_revised` void is appended; scoring keeps
   the first resolution so the outcome cannot be re-chosen later.
8. **Is this tamper-proof?**
   No, it is tamper-evident. A determined operator could rewrite the branch, but it would
   be visible to anyone holding an earlier clone, and the GitHub Actions logs would not
   match. I say that openly on the Methods page.
9. **How do you test it?**
   Unit tests for every invariant, plus Hypothesis property tests: any single-byte change
   in a sealed file is detected, and any forecast after the lock fails verification for
   any delay. Hypothesis found one real bug: invalid UTF-8 crashed `verify` instead of
   being reported.
10. **When does the "official" record start, and why not immediately?**
   After five consecutive clean days (successful morning run, no failed run, all health
   checks passed, day sealed), decided by code from the ledger and written once. A
   rehearsal period catches operational bugs before they can contaminate the record that
   the hypotheses are judged on.
