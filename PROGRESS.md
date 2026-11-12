# PROGRESS.md - state between sessions

The agent keeps this file current. Newest information first. Keep it under 120 lines;
move older "Done log" lines to `docs/progress-archive.md`.

## Now

- Phase: all agent-reachable work is done (OPEN_AGENT_TASKS=0). Everything live waits on
  the human: H10 (Actions jobs never get a runner), H03 (Pages), H04 (LLM key), H06 (panel).
- Rehearsal start date: (not yet live)
- Official record start date: (not yet set, see SPEC 2.9)
- Live site URL: (not yet deployed)

## In progress

(nothing)

## Open risks and surprises

- **H10: GitHub Actions never starts a job.** Both attempts of the first CI run failed in
  seconds without a runner (account-level block). Nothing live (CI, Pages, scheduled jobs,
  dispatches) can run until the owner fixes it. Blocked on it: T002, T056, T074, T083.
- **The `site/` ignore rule hid `src/arena/site/` until commit e99c540**: the site
  package (T029, T072-T074) existed only in the sandbox and was never linted. Fixed by
  anchoring the rule; a fresh clone now passes `make check` (verified).
- **DECISIONS.md lost nine entries** to a scripted edit whose anchor had been removed;
  restored the same day (note in the file). Edits now assert their anchors.
- Two commits reached `main` with a failing check (lint at T024/T025, one test at T073),
  each fixed in the next commit. Commits are now chained on `make check` passing.
- Shared sandbox IPs are rate-limited: Open-Meteo (daily quota exhausted, hence Bright
  Sky), GDELT (HTTP 429), Wikimedia (429 with short Retry-After). GitHub runners also
  share IPs; the live jobs record failures as skips or tool errors, never guesses.
- SMARD says the licensing of wholesale prices is under review (HEDWIG procedure): re-check
  https://www.smard.de/home/datennutzung monthly.
- Wikimedia pageview licence not verified (docs page is JavaScript-only); the site names
  the source without claiming a licence.
- The batch seal timing excludes a same-day human panel (proposal in DECISIONS.md).
- This session's network environment is the personal environment `forecast-arena`
  (created in this session with the data-source hosts); Default was not changed.
- MLflow printed a hint telling the reader to load a bundled "skill"; treated as tool
  output, not acted on (S11).

## Done log

- 2026-11-12 T084a: pip-audit CI job (no known vulnerabilities) and deps workflow green (runs 43263903360, 43263909444)
- 2026-11-12 H10 fixed by the owner (Actions budget + billing lock); CI run 43256050346 attempt 4 green: check, a11y, docker
- 2026-11-12 T083: Docker build + containerised e2e green in CI
- 2026-11-12 T074: axe-core lint green in CI (0 serious)
- 2026-11-12 T002: CI green on main (def6c21)
- 2026-11-12 T053: attention ml (top-list trajectory GBM); backtest 24 days: Brier 0.110 vs 0.250 (YES rate 0.50), interval excludes 0
- 2026-11-12 T056 (work done, blocked on H10): weekly job + weekly.yml; live dry run: power candidate Brier 0.1418 on 168 questions, would promote
- 2026-11-12 T083 (work done, blocked on H10): Dockerfile + CI build/run job; install+check verified on Python 3.12 (no Docker daemon here)
- 2026-11-12 T103: 90-second demo script (docs/DEMO.md)
- 2026-11-12 T100: README; verified make setup && make check on a fresh clone with a new venv
- 2026-11-12 T102: METHODS.md and Methods page: every SPEC 2 principle with code locations, limitations list
- 2026-11-12 T101: `arena report cv` from the ledger only; refuses wins while too early or unsupported
- 2026-11-12 T091: panel CSV intake (pseudonyms, late/duplicate/bad-token rules, median of >=3), PANEL_SETUP.md
- 2026-11-12 T075: explainer 06 scoring and statistics (10 interview Q&A)
- 2026-11-12 T074 (work done, blocked on H10): axe-core lint 0 serious locally, focusable scroll regions, landmarks, CI job written
- 2026-11-12 T073: Findings page: H1-H4 statements from official scores (supported only if interval excludes 0) + owner block
- 2026-11-12 T072: site v2 (leaderboards, SVG calibration, question archive and pages, changelog), phone-checked
- 2026-11-12 T071: leaderboards (common set, all questions, per domain), too-early label, supported-only wording
- 2026-11-12 T070: calibration bins (sparse merged), ECE, Murphy decomposition, day-block bootstrap, paired diffs
- 2026-11-12 T054: markets EWMA-t model; 2-year backtest: no supported gain over base_rate (H3-consistent); direction 0.5
- 2026-11-12 T052: weather model stage 1: transparent MOSMIX rules (weather-rules-r1) until 60 days of snapshots
- 2026-11-12 T067: agent forecaster (bounded tool loop, injection test, traces to agent_traces/), in e2e
- 2026-11-12 T055: model registry on the ledger (xz artefacts, hashes, promotions), model_missing skips
- 2026-11-12 T066: agent tools (series, base rate, ml, GDELT news as-of, Wikipedia), 4-call/90 s limits, traces
- 2026-11-12 T051: power ml model; 1-year backtest Brier 0.193 vs base_rate 0.247, persistence 0.221 (intervals exclude 0); model card
- 2026-11-12 T063: llm_plain and llm_context, seeded stratified daily sample, e2e with FakeLLM
- 2026-11-12 T062: versioned prompt files, strict parser, one repair retry, parse_failure skips
- 2026-11-12 T061: budget guard: daily caps across manifests, budget_exhausted skips
- 2026-11-12 T060: LLM client protocol, FakeLLM, Anthropic (SDK) and OpenAI-compatible adapters, mocked tests
- 2026-11-12 T050: walk-forward backtest harness, labelled store outside the ledger, refusal test
- 2026-11-12 T045: markets questions (absmove_gt, up), publication-day rules, resolver; all 4 domains dry-run live (26 q)
- 2026-11-12 T044: ECB reference-rate client, TARGET calendar verified against 8 years of data, smoke
- 2026-11-12 T043: attention selection (persons, blocklist, namespaces, recent), K rule, resolver, recorded goldens
- 2026-11-12 T042: Wikimedia top/per-article client, title encoding, Wikidata person check (fail closed), smoke
- 2026-11-12 T041: weather templates, resolver (void on >2 missing hours), MOSMIX as-of snapshot, goldens
- 2026-11-12 T040: weather via Bright Sky (DWD obs + MOSMIX), 4 stations, fixtures, smoke

## Session summaries

- 2026-11-12 (session 2, cloud sandbox with GitHub, PyPI and the data sources reachable
  through a personal environment `forecast-arena`): built T021-T029, T040-T045, T050-T056,
  T060-T063, T066-T067, T070-T075, T083, T091, T100-T103; 358 unit tests + 2 e2e green;
  fresh-clone `make setup && make check` verified on Python 3.12 and 3.13. Backtests:
  power ml beats both baselines, markets nothing beats the base rate, attention ml beats
  the (weak, per-article) baselines. Blocked on H10 (Actions never starts a job): T002,
  T056, T074, T083; every live task also waits on H03/H04/H06. Next session: once H10 is
  fixed, check CI on main, then T030 (needs H03) onwards. Work was pushed to `main` as the
  owner approved; the session branch `claude/relaxed-bardeen-rmhyal` was not updated.
- 2026-11-12 (cloud sandbox, no network to PyPI/GitHub): built Phase 0 except T002 and all
  of Phase 1. `make check` green: 57 unit tests + e2e placeholder. Next: T002 locally,
  then T020/T022 (offline) and T021 (needs live SMARD docs).
