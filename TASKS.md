# TASKS.md - backlog

Work top to bottom. `python scripts/status.py` prints the next ready task.

Legend: `[ ]` open, `[x]` done, `[!]` blocked or waiting (reason appended, see AGENTS.md 2.4).
`deps:` tasks that must be done first. `needs:` items in HUMAN_TODO.md the human must tick.
`(live)` marks tasks that change the public pipeline: be extra careful and verify after.
Section numbers refer to docs/SPEC.md. Every task also requires `make check` to pass.

Keep the first line of each task in exactly this shape; the status script parses it.

## Phase 0 - Bootstrap

- [x] T001 · Repository skeleton and tooling (deps: -)
  - Do: `pyproject.toml` (package `arena`, Python >= 3.12, `src/` layout), lock file, lint
    and test config, `Makefile` with `setup`, `lint`, `test`, `e2e` (no-op for now),
    `check`, `status`, `smoke-sources`; MIT `LICENSE`; `README.md` stub; extend `.gitignore`.
  - Done when: `make setup && make check` exit 0; `python -c "import arena"` works.
- [!] T002 · CI workflow (deps: T001) BLOCKED(needs H10)
  - Do: `.github/workflows/ci.yml` running `make check` on push and pull request to `main`.
    Look up current action versions and record them in `docs/SOURCES.md`.
  - Done when: `gh run list --branch main --limit 1` shows a successful run of this commit.
- [x] T003 · Config and clock (deps: T001)
  - Do: `arena.config` (typed settings from `ARENA_*` environment variables with defaults;
    no secrets in code); `arena.clock` (`Clock` protocol, `SystemClock`, `FixedClock`).
  - Done when: unit tests cover defaults, overrides and a fixed clock.
- [x] T004 · Core schemas (deps: T003)
  - Do: pydantic v2 models for section 5; canonical JSON serialisation (sorted keys,
    UTF-8, newline-terminated); JSON Schemas exported to `docs/schemas/`.
  - Done when: round-trip and validation tests pass; a schema-drift test fails if models
    change without re-exporting.
- [x] T005 · Documentation scaffolding (deps: T001)
  - Do: `docs/SOURCES.md` (table: fact, source URL, date checked), `docs/RUNBOOK.md` stub,
    `docs/METHODS.md` stub, `docs/explainers/README.md`.
  - Done when: files exist and are linked from `README.md`.

## Phase 1 - Ledger

- [x] T010 · Append-only ledger storage (deps: T004)
  - Do: `arena.ledger` reader and writer over a directory with the layout of section 6:
    atomic writes, schema validation on write and read, duplicate-id rejection.
  - Done when: tests prove appends never change earlier bytes, a simulated crash leaves no
    partial file, and duplicates are refused.
- [x] T011 · Seals and hash chain (deps: T010)
  - Do: batch seal, day seal, chain, and `arena ledger verify` as in section 6.
  - Done when: tamper tests (edit, delete, reorder, forecast after lock) each make `verify`
    fail with a clear message; an untouched ledger passes.
- [x] T012 · Git sync for the ledger branch (deps: T010)
  - Do: helpers that check out `ledger` into `./_ledger` (creating the orphan branch if
    absent), commit as `ledger: <job> <date>`, pull with rebase and retry on conflict, and
    never force.
  - Done when: tests against a temporary bare repository cover first run, normal run and
    a simulated concurrent push.
- [x] T013 · Commit-time verification (deps: T011, T012)
  - Do: `arena ledger verify --git` checks from branch history that each batch commit
    landed before its lock time. Write the honest limits of this evidence into
    `docs/METHODS.md`.
  - Done when: tests with a fabricated late commit fail verification.
- [x] T014 · Run manifests (deps: T010)
  - Do: a context manager that records job, date, code SHA, package versions, timings,
    counts, warnings and LLM usage to `runs/`.
  - Done when: tests show a manifest is written on success and on failure.
- [x] T015 · Command-line interface (deps: T014)
  - Do: `arena` CLI with groups `questions`, `forecast`, `resolve`, `score`, `site`,
    `ledger`, `daily`, `report`; common options `--date`, `--dry-run`, `--ledger-dir`.
  - Done when: `arena --help` lists the groups and CLI tests pass.

## Phase 2 - Power domain, baselines, first live day

- [x] T020 · HTTP layer (deps: T003)
  - Do: shared HTTP client: timeouts, retries with backoff, identifying User-Agent (from
    `ARENA_CONTACT`, else the repository URL), optional response snapshot to disk.
  - Done when: tests with a mocked transport cover retry, timeout and User-Agent.
- [x] T021 · SMARD client (deps: T020)
  - Do: verify section 7.1 against the live service and current community docs; implement
    chunk index and series fetch returning a tidy UTC-indexed frame; handle nulls and
    weekly chunks; record small real fixtures with provenance.
  - Done when: unit tests pass on fixtures including a clock-change week;
    `make smoke-sources` fetches the latest day-ahead prices.
- [x] T022 · Domain contract and registry (deps: T004)
  - Do: the `Domain` protocol of section 7.0, a registry, the as-of gateway helper, the
    degeneracy rule, and a toy domain for tests.
  - Done when: tests show the gateway never returns a value newer than `asof`.
- [x] T023 · Power history and availability rules (deps: T021, T022)
  - Do: fetch trailing windows for daily jobs; a full-history backfill into a git-ignored
    cache for training; conservative availability rules documented in `docs/SOURCES.md`.
  - Done when: backfill completes and prints a summary; cache is not tracked by git.
- [x] T024 · Power question templates (deps: T023)
  - Do: the six templates of section 7.1 with thresholds, ids, texts and params.
  - Done when: golden tests on fixed fixture dates (ordinary day, both clock-change days,
    a holiday) match; generation is deterministic.
- [x] T025 · Power resolver (deps: T024)
  - Do: resolution, evidence snapshot, grace period, void rules, revision detection.
  - Done when: tests cover a normal day, missing hours, a 23-hour and a 25-hour day.
- [x] T026 · Forecaster contract and baselines (deps: T022)
  - Do: `Forecaster` protocol; `base_rate` (8.1) and `persistence` (8.2), using history
    replayed through the real question and resolver code.
  - Done when: tests cover smoothing, the under-10-instances rule and the fallback.
- [x] T027 · Daily jobs and offline end-to-end test (deps: T015, T025, T026)
  - Do: `arena daily morning` and `arena daily resolve`: idempotent, lock-time enforced
    (late runs record a miss and write no forecasts), a failed forecaster never aborts the
    batch. `make e2e` simulates five days offline; add it to `make check`.
  - Done when: `make e2e` passes; running a job twice for one date changes nothing.
- [x] T028 · Scoring v1 (deps: T027)
  - Do: Brier, log score, skill against `base_rate`, counts, clipping (section 10).
  - Done when: property tests pass (perfect = 0, constant 0.5 = 0.25).
- [x] T029 · Static site v1 (deps: T028)
  - Do: `arena site build`: Home, Methods stub, Status, About placeholder; disclaimer and
    attributions on every page; responsive; light and dark theme.
  - Done when: the site builds from the e2e ledger; an internal link check passes.
- [ ] T030 · Scheduled workflows (live) (deps: T027, T029; needs: H03)
  - Do: `morning.yml`, `resolve.yml` per sections 4 and 12 with a `dry_run` input, shared
    concurrency group, minimal permissions, ledger push and Pages deploy.
  - Done when: `gh workflow run morning.yml -f dry_run=true` and the same for `resolve.yml`
    finish successfully.
- [ ] T031 · Promotion to stable (live) (deps: T030)
  - Do: `promote.yml` fast-forwards `stable` after CI succeeds on `main`; scheduled jobs
    check out `stable`.
  - Done when: after a green CI run, `stable` and `main` point to the same commit.
- [ ] T032 · Rehearsal go-live (live) (deps: T031)
  - Do: trigger a real morning run; confirm the ledger branch holds today's questions,
    forecasts and batch seal committed before lock; confirm the site is reachable at the
    Pages URL; write "Daily operations" and "If something breaks" in `docs/RUNBOOK.md`;
    record the rehearsal start date in `PROGRESS.md` and `README.md`.
  - Done when: `arena ledger verify --git` passes on the real ledger and the Pages URL
    returns the Home page.
- [ ] T033 · Health checks and incident issues (live) (deps: T032)
  - Do: the health checks and alert behaviour of section 12.
  - Done when: a deliberately failing dry run opens one `incident` issue and a following
    healthy run closes it.
- [ ] T034 · Next-day verification (deps: T032)
  - Do: at least one day after T032, confirm questions resolved, scores appeared, the day
    seal exists and verify passes. Fix anything found. If it is too early, mark this task
    `WAIT(until=<date>)`.
  - Done when: the Status page shows one fully resolved batch.
- [ ] T035 · Official-start rule (deps: T033)
  - Do: implement principle 2.9: clean-day streak tracking, one-time write of
    `meta/official_start.json`, rehearsal banner on the site, exclusion from headline scores.
  - Done when: tests cover a streak broken by an incident and the one-time write.
- [ ] T036 · Explainers 01 and 02 (deps: T032)
  - Do: `docs/explainers/01-ledger-and-forecast-before-truth.md` and
    `02-power-market-questions.md` in the format of AGENTS.md section 8.
  - Done when: both files exist, each with ten interview questions and answers.

## Phase 3 - More domains

- [x] T040 · Weather sources (deps: T022, T020)
  - Do: verify and choose the forecast source and the observation source (section 7.2);
    clients, station mapping in config, fixtures, decision recorded.
  - Done when: unit tests pass; `make smoke-sources` fetches a forecast and yesterday's
    observations for each city.
- [x] T041 · Weather questions, resolver, as-of snapshot (deps: T040)
  - Do: templates and resolver of section 7.2; the morning job stores the forecast values
    it saw under `snapshots/weather/`.
  - Done when: golden tests pass, including a day with missing observations (void).
- [x] T042 · Wikimedia pageviews client (deps: T020)
  - Do: verify section 7.3; top-list and per-article fetch, title encoding, lag handling,
    Wikidata person check; fixtures.
  - Done when: unit tests pass; `make smoke-sources` fetches the latest published top list.
- [x] T043 · Attention questions and resolver (deps: T042, T022)
  - Do: selection rules, exclusions, blocklist config, template and resolver (7.3).
  - Done when: golden tests show person articles and blocklisted titles are never
    selected, and selection is deterministic for a batch date.
- [x] T044 · ECB reference-rate client (deps: T020)
  - Do: verify the official endpoint and terms (7.4); client; publication-day calendar.
  - Done when: unit tests pass on fixtures; `make smoke-sources` fetches the latest fixing.
- [x] T045 · Markets questions and resolver (deps: T044, T022)
  - Do: templates and resolver of section 7.4.
  - Done when: tests cover a Friday batch, a weekend (no questions) and a holiday.
- [ ] T046 · Enable the new domains (live) (deps: T041, T043, T045, T034)
  - Do: extend the e2e test to all four domains, then enable them in the live config.
  - Done when: the next real morning run writes questions for all applicable domains and
    verify passes. If that run has not happened yet, mark `WAIT(until=<date>)`.
- [ ] T047 · Explainer 03 (deps: T046)
  - Do: `docs/explainers/03-question-design-and-base-rates.md`.
  - Done when: the file exists in the required format.

## Phase 4 - Classical ML forecasters

- [x] T050 · Backtest harness (deps: T027)
  - Do: walk-forward replay through the real question, context and resolver code into a
    separate `backtests/` store, labelled as backtest everywhere (integrity rule I4).
  - Done when: a test proves backtest records cannot be written to the live ledger.
- [ ] T051 · Power model (deps: T050, T023)
  - Do: section 8.3 power model, validation, calibration, model card. Measure for seven
    days whether official day-ahead forecasts are published before lock before using them.
  - Done when: the backtest report compares `ml` with `base_rate` and `persistence` with
    intervals. Ship it even if it does not win, and say so on the model card.
- [ ] T052 · Weather model (deps: T050, T041)
  - Do: section 8.3 weather model; rule-based version until 60 days of snapshots exist.
  - Done when: the forecaster returns probabilities for both templates in tests.
- [ ] T053 · Attention model (deps: T050, T043)
  - Do: section 8.3 attention model with backtest and model card.
  - Done when: the backtest report exists with intervals.
- [ ] T054 · Markets model (deps: T050, T045)
  - Do: section 8.3 volatility model; direction fixed at 0.5 unless skill is shown.
  - Done when: the backtest report exists; the direction decision is recorded.
- [ ] T055 · Model registry (deps: T051)
  - Do: versioned artefacts with metadata under `models/` on the ledger; loading by
    version; `model_missing` skip when absent.
  - Done when: tests cover load, missing model and version reporting.
- [ ] T056 · Weekly retraining workflow (live) (deps: T055, T052, T053, T054)
  - Do: `weekly.yml` per section 12: retrain, compare, promote by rule, model card, MLflow
    file-backed run with a published summary.
  - Done when: a `dry_run=true` dispatch succeeds and prints the promotion decision.
- [ ] T057 · Enable the ML forecaster (live) (deps: T056, T046)
  - Do: turn on `ml` in the live config after the e2e test includes it.
  - Done when: a real morning run records `ml` forecasts for every question, or
    `WAIT(until=<date>)` until that run exists.
- [ ] T058 · Explainer 04 (deps: T057)
  - Do: `docs/explainers/04-ml-models-leakage-calibration.md`.
  - Done when: the file exists in the required format.

## Phase 5 - LLM forecasters

- [x] T060 · LLM client (deps: T003)
  - Do: section 9.1: protocol, `FakeLLM`, two adapters written against current official
    API documentation, usage accounting.
  - Done when: adapter tests pass with mocked HTTP; no test needs a key.
- [x] T061 · Budget guard (deps: T060, T014)
  - Do: section 9.4 caps counted across all runs of a UTC day.
  - Done when: tests show the cap stops calls and produces `budget_exhausted` skips.
- [x] T062 · Prompts and strict parsing (deps: T060)
  - Do: section 9.2: versioned prompt files, strict parser, one repair retry.
  - Done when: tests with malformed outputs produce `parse_failure` skips, never a number.
- [x] T063 · Plain and context LLM forecasters (deps: T061, T062, T027)
  - Do: `llm_plain`, `llm_context`, and the seeded stratified daily sample (8.4).
  - Done when: e2e with `FakeLLM` shows all LLM forecasters answering the same sample.
- [ ] T064 · Live LLM smoke workflow (deps: T063; needs: H04)
  - Do: `llm-smoke.yml` (manual, two calls, prints usage, writes nothing).
  - Done when: a dispatch succeeds and reports token usage.
- [ ] T065 · Enable plain and context LLM forecasters (live) (deps: T064, T046)
  - Do: enable both in the live config.
  - Done when: a real morning run records their forecasts within the caps, or
    `WAIT(until=<date>)`.
- [ ] T066 · Agent tools (deps: T063)
  - Do: section 9.3 tools; verify terms and choose news backends; compact trace logging.
  - Done when: tests cover each tool, the call limit and the time limit.
- [ ] T067 · Agent forecaster (deps: T066, T055)
  - Do: tool-use loop with `FakeLLM`-scripted tests; injection hygiene in the prompt;
    headline-only storage.
  - Done when: a test with a tool result containing instructions shows they are ignored
    by the harness (no extra tool calls, no changed output contract).
- [ ] T068 · Enable the agent forecaster (live) (deps: T067, T065; needs: H04)
  - Do: enable `agent` in the live config.
  - Done when: a real morning run records agent forecasts and traces within the caps, or
    `WAIT(until=<date>)`.
- [ ] T069 · Explainer 05 (deps: T068)
  - Do: `docs/explainers/05-llm-forecasters-and-agent.md`, including costs and failure modes.
  - Done when: the file exists in the required format.

## Phase 6 - Statistics and the full site

- [ ] T070 · Statistics (deps: T028)
  - Do: calibration bins, calibration error, Murphy decomposition, day-block bootstrap,
    paired differences (section 10).
  - Done when: tests on synthetic data with known answers pass; results are seed-stable.
- [ ] T071 · Leaderboards (deps: T070)
  - Do: common-set and all-question boards, per domain, with the wording rules.
  - Done when: tests cover the "too early to tell" label and common-set selection.
- [ ] T072 · Site v2 (deps: T071)
  - Do: all pages of section 11 except Findings; question archive and per-question pages;
    version changelog; About from `site_content/` with a placeholder if absent.
  - Done when: the site builds from the e2e ledger; link check passes; pages render at
    phone width.
- [ ] T073 · Findings page (deps: T072)
  - Do: templated factual statements about H1-H4 from the scores, plus the human block
    from `site_content/findings.md` (placeholder if absent).
  - Done when: tests show no statement claims support unless the interval excludes zero.
- [ ] T074 · Accessibility and performance pass (deps: T072)
  - Do: semantic HTML, contrast, keyboard use, charts readable without colour alone,
    small page weight; link check in CI.
  - Done when: an automated accessibility lint run in CI reports no serious issues.
- [ ] T075 · Explainer 06 (deps: T071)
  - Do: `docs/explainers/06-scoring-and-statistics.md`.
  - Done when: the file exists in the required format.

## Phase 7 - Operations and monitoring

- [ ] T080 · Status page (deps: T072, T033)
  - Do: last runs, missed days, voids, parse failures, LLM usage, source freshness.
  - Done when: the page builds from the e2e ledger with all panels populated.
- [ ] T081 · Drift monitoring (deps: T056)
  - Do: weekly Evidently report (feature drift, prediction drift, performance over time)
    published under the Status page.
  - Done when: the weekly dry run produces the report from fixture data.
- [ ] T082 · Experiment summary (deps: T056)
  - Do: export MLflow run summaries to a page linked from Status; record in `DECISIONS.md`
    whether a remote tracking server is worth a human item (default: no).
  - Done when: the page lists at least the fixture runs.
- [ ] T083 · Dockerfile (deps: T027)
  - Do: image that runs `make e2e`; CI builds it (no registry push).
  - Done when: `docker build` and the containerised e2e succeed in CI.
- [ ] T084 · Dependency hygiene (deps: T002)
  - Do: vulnerability audit in CI as a non-blocking report; a monthly workflow that opens
    an issue listing outdated pins (no automatic merges).
  - Done when: both workflows run successfully once.
- [ ] T085 · Explainer 07 (deps: T080)
  - Do: `docs/explainers/07-operations-and-monitoring.md`.
  - Done when: the file exists in the required format.

## Phase 8 - Ensemble and human panel

- [ ] T090 · Ensemble forecaster (deps: T071, T057)
  - Do: section 8.6 with walk-forward training and the activation threshold.
  - Done when: tests show it stays inactive below the threshold and trains only on
    resolved official-record forecasts.
- [ ] T091 · Human panel intake (deps: T027)
  - Do: section 8.7 CSV adapter, validation, pseudonyms, median rule; fixtures;
    `docs/PANEL_SETUP.md` with step-by-step instructions for the human.
  - Done when: tests cover late rows, duplicate rows, bad tokens and fewer than 3 answers.
- [ ] T092 · Enable the human panel (live) (deps: T091, T046; needs: H06)
  - Do: enable intake in the morning job.
  - Done when: a real morning run ingests panel rows, or `WAIT(until=<date>)`.
- [ ] T093 · Enable the ensemble (live) (deps: T090, T068)
  - Do: enable once the activation threshold is met on the real ledger.
  - Done when: the ensemble appears on the leaderboard, or `WAIT(until=<date>)` with the
    current count recorded in `PROGRESS.md`.

## Phase 9 - Finish

- [ ] T100 · README (deps: T072)
  - Do: what it is, live link, architecture diagram, how it works, how to reproduce, data
    attribution, limitations, how it was built.
  - Done when: a newcomer can run `make setup && make check` from the README alone.
- [ ] T101 · CV numbers report (deps: T071)
  - Do: `arena report cv` prints days live, resolved forecasts and headline scores with
    intervals from the ledger only.
  - Done when: a test shows it refuses to print a comparison labelled "too early to tell"
    as a win.
- [ ] T102 · Methods and limitations (deps: T072)
  - Do: complete `docs/METHODS.md` and the Methods page, including every known limitation.
  - Done when: each principle of section 2 is explained with where it is enforced in code.
- [ ] T103 · Demo outline (deps: T100)
  - Do: `docs/DEMO.md`: a 90-second screen-recording script for the human to record.
  - Done when: the file exists.
- [ ] T104 · Final audit (deps: T100, T101, T102, T103, T085, T075, T069, T058, T047, T036)
  - Do: run verify on the real ledger, the full check suite and the link check; confirm
    every explainer exists; summarise state, open risks and suggested next steps in
    `PROGRESS.md`.
  - Done when: all of the above pass and the summary is written.
