# Progress archive

Older "Done log" lines moved from docs/project/PROGRESS.md (newest first).

- 2026-11-12 T029: static site v1 (Home, Methods, Status, About), disclaimer/attribution on every page, light/dark, link check
- 2026-11-12 T028: scoring v1 (clip, Brier, log, skill vs base_rate, counts), property tests, `arena score show`
- 2026-11-12 T027: daily morning/resolve jobs (lock enforced, idempotent, error skips, revisions), replay history, 5-day e2e
- 2026-11-12 T025: power resolver (grace void, ties, 23/25h days, revision detection)
- 2026-11-12 T024: six power templates; golden tests (ordinary, 23h, 25h, Christmas) on real SMARD fixtures
- 2026-11-12 T023: power history/as-of store; live backfill 424 chunks, 2964 complete days, 0 gaps
- 2026-11-12 T021: SMARD client (index, weekly chunks, nulls, Berlin days, cache), fixtures, smoke
- 2026-11-12 T026: base_rate and persistence baselines, LedgerHistory/StaticHistory
- 2026-11-12 T022: domain contract, as-of gateway, degeneracy rule, registry, toy domain
- 2026-11-12 T020: stdlib HTTP client (retries, backoff, User-Agent, snapshots)
- 2026-11-12 T002 (part): ci.yml written with verified action versions; tick after first green run
- 2026-11-12 T015: arena CLI with all groups; ledger verify / seal-batch / seal-days
- 2026-11-12 T013: verify --git checks batch commits landed before lock; limits in METHODS
- 2026-11-12 T014: run manifests on success and failure
- 2026-11-12 T012: ledger git sync (orphan create, clone, rebase-retry push, never force)
- 2026-11-12 T011: batch/day seals, hash chain, verify with tamper tests
- 2026-11-12 T010: append-only ledger storage, atomic writes, duplicate refusal
- 2026-11-12 T005: docs scaffolding
- 2026-11-12 T004: pydantic schemas, canonical JSON, exported JSON Schemas
- 2026-11-12 T003: settings and clock
- 2026-11-12 T001: skeleton, Makefile, pinned deps
- 2026-11-13 T033: health checks + incident issue live-tested: failing dry run 43396287940 opened issue #1, healthy dry run 43397819217 closed it
- 2026-11-13 T118: Hypothesis property tests (round-trip, scoring bounds, any changed byte detected, late forecasts rejected) found a real bug: verify crashed on non-UTF-8 bytes -> now a LedgerError; pytest-cov in CI summary (87% coverage)
- 2026-11-13 T117: power analysis (days needed to detect a 0.01/0.02 Brier gap at 80% power) on Findings
- 2026-11-13 T113: PyTorch quantile MLP ties the champion in the 1-year power backtest (0.1927 vs 0.1930, diff -0.0003 [-0.0087, +0.0081], DM p=0.95): published honestly in docs/models/power-mlp.md
- 2026-11-13 T115: conformalized quantile regression (CQR) for the power 80/90% bands in the weekly job and on Experiments; synthetic test restores 38% -> ~80% coverage
- 2026-11-13 T112: LightGBM + Optuna challenger beats the champion in the 1-year power backtest (Brier 0.1884 vs 0.1930, diff -0.0045 [-0.0069, -0.0021], DM p<0.001); card docs/models/power-lgbm.md
- 2026-11-13 T032: first real batch (6 power questions, 18 forecasts incl. Claude Haiku 5.5) on the ledger at 08:27 UTC, before the 09:30 lock; verify --git PASS; rehearsal start 2026-11-13. Both morning schedules were skipped by GitHub; dispatched by hand from `stable` (run 43393206918)
- 2026-11-13 fix: agent repair step re-sent the model's reply (two assistant turns in a row -> API 400 on thinking blocks); regression test; workflows default ARENA_LLM_EFFORT=low so thinking does not use the 400-token answer budget
- 2026-11-13 T111: weekly job trains several candidate families per domain, promotes the best only if not worse than the champion; candidates table on Experiments
- 2026-11-13 Phase 0: roadmap tasks T110-T171 in docs/project/TASKS.md, H15-H19, decisions, SPEC 8.8/11 amendments; scheduled resume every 5 h (trig_016b95iyHSuR6B44xPaAgDPF)
- 2026-11-13 owner approved docs/ROADMAP.md (portfolio roadmap v2); next session starts with its Phase 0 (add tasks T110+ to docs/project/TASKS.md), then Phase 1
- 2026-11-12 T045m: pinball loss + interval coverage in weekly job; forest plot, podium, architecture, About
- 2026-11-12 site round 4 (owner request): leaderboard podium + forest plot (CIs), architecture diagram (methods/stack/about), About page with author card and skills grid
- 2026-11-12 H05 published (owner details: name, 35390 Gießen, e-mail, Hesse/HBDI); H14 open for street address
- 2026-11-12 H05 drafts written at owner request (docs/legal/, placeholders, never published unfinished)
- 2026-11-12 pages v2 (owner request): shared page headers; calibration cards with metrics; findings progress + hypothesis cards; status health banner, schedule timeline, skip explanations
- 2026-11-12 T045i-l (owner request): DuckDB SQL + Parquet open data, Diebold-Mariano, permutation importance, mypy clean in make check
- 2026-11-12 home v3 (owner request): hero with live standings, KPIs, biggest-disagreement spotlight, race chart (validated palette), topic tiles, trust pillars; mobile nav; package data includes feed.xml
- 2026-11-12 owner decision: zero-ish cost; stay on Haiku 5.5, daily token cap 150000 in workflows (~$1/month max); H13 declined
- 2026-11-12 T045h (owner request): tech stack page, LLM effort setting, H13 (optional frontier model)
- 2026-11-12 T045f/T045g (owner request): guide, imprint/privacy, question verdicts, archive filters, leaderboard bars, feed, 404; docs/COMPLIANCE.md; a11y 0 serious
- 2026-11-12 T045d (owner request): crypto domain (CoinGecko, 5 coins, up/bigmove), off until H12; terms page read refused by permission system (recorded in H12)
- 2026-11-12 site redesign live (resolve run 43300900342); manual dispatches must use --ref main (Pages environment allows main only)
- 2026-11-12 T045a-c (owner request): plain question titles; weather duels warmer_than/wetter_than; frost_day, gust_gt; weather-rules-r2; v1 weather questions byte-identical (frozen goldens)
- 2026-11-12 stock data research (H08): US/India(NSE)/Germany(DAX) index data all need a licence or written permission; nothing built
- 2026-11-12 site live: real resolve run 43295826086 created the ledger branch, verify PASS, Pages deployed to https://jashd12.github.io/forecast-arena/ (T032 still waits for the first morning batch)
- 2026-11-12 T064: llm-smoke run 43294520796 green: anthropic/claude-haiku-5-5, contract ok, tool round-trip ok, 2 requests, 762 in / 215 out tokens
- 2026-11-12 T032 waiting: first real morning run is the scheduled 05:30 UTC run on 2026-11-13 (from stable); RUNBOOK written
- 2026-11-12 T031: promote.yml green; stable == main == 48e7b5b
- 2026-11-12 T030: morning.yml + resolve.yml dry-run dispatches green (runs 43286773304, 43286778910)
- 2026-11-12 T082: experiments page from weekly summaries; no remote tracking server (DECISIONS)
- 2026-11-12 T081: Evidently drift metrics in weekly summaries (fixture test green in CI), HTML as artifact
- 2026-11-12 T056: weekly dry-run dispatch 43277710606 green; printed decisions (attention 0.1089 n=224, power 0.1418 n=168)
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
- 2026-11-13 T035+T110: clean-day streak from run manifests, recorded health reports and day seals; official start written once (write_raw refuses a second write); not-before gate (default 2099-12-31 until roadmap changes are live); streak on Status
- 2026-11-13 T036: explainers 01 (ledger, forecast before truth) and 02 (power questions), ten Q&A each
- 2026-11-13 T080: Status page adds missed days, source freshness (latest batch/answer, overdue), LLM usage per day vs cap, LLM parse-failure rates; e2e now records usage like the CLI
- 2026-11-13 T085: explainer 07 (operations and monitoring) with real incidents

## Resolved risks (moved from docs/project/PROGRESS.md on 2026-11-13)

- **H10: GitHub Actions never starts a job.** Both attempts of the first CI run failed in
  seconds without a runner (account-level block). Nothing live (CI, Pages, scheduled jobs,
  dispatches) can run until the owner fixes it. Blocked on it: T002, T056, T074, T083.
- **The `site/` ignore rule hid `src/arena/site/` until commit e99c540**: the site
  package (T029, T072-T074) existed only in the sandbox and was never linted. Fixed by
  anchoring the rule; a fresh clone now passes `make check` (verified).
- **docs/project/DECISIONS.md lost nine entries** to a scripted edit whose anchor had been removed;
  restored the same day (note in the file). Edits now assert their anchors.
- Two commits reached `main` with a failing check (lint at T024/T025, one test at T073),
  each fixed in the next commit. Commits are now chained on `make check` passing.

## Moved from PROGRESS.md on 2026-11-14

## Phase 11 (owner approved 2026-11-13 evening)

- Review plan approved; tasks T180-T192 in docs/project/TASKS.md. First evening run dispatched by hand
  at 19:29 UTC (scheduled one had not started): 6 power questions for 2026-11-14, all
  `-v2`, lock 09:30 unchanged, `ledger verify` passes. T180 (due-gate, frequent crons)
  pushed; it waits for 2026-11-14 to show a batch sealed before the lock without help.
  A one-shot check at 05:45 UTC dispatches the morning run if no batch seal exists.

## Session summary (2026-11-13, evening)

- Done and pushed: T142 (README), T160 (evening publication, `evening.yml` from 18:00
  UTC), T161 (players intake, `players.yml`, live after H15), T170 (interview kit),
  T171 (honesty audit), and a bug fix for the live agent (Anthropic thinking blocks).
- Learned: a manual dispatch on `stable` cannot deploy Pages (the deploy job failed while
  the resolve itself succeeded); dispatch from `main` as AGENTS.md says. Scheduled
  resolve runs start hours late; the twice-a-run design absorbs it.

- 2026-11-13 T131: question page chart from the morning snapshot (per-domain series, threshold, observed value, data table) and previous/next links
- 2026-11-13 T130: play.html "Can you beat the AI?" (live + practice decks, in-memory score), self-hosted app.js, CSP on every page, Playwright round test in make a11y, home teaser, nav link
- 2026-11-13 T125: arena mcp, read-only MCP server (official SDK 2.3.0): list_questions, get_question, leaderboard, run_sql (single SELECT, DuckDB external access off); stdio test; README setup
- 2026-11-13 T124 follow-up: first real evals showed 400-token cap truncating thinking answers; cap now from settings (workflow default 1024) and in every LLM version string
- 2026-11-13 T124: eval harness (frozen golden set of 186 past power questions, llm_plain vs llm_context A/B, Brier/log/ECE/skill/JSON validity/repairs/cost), FakeLLM CI gate, manual llm-eval.yml, evals.html (EVALUATION banner)
- 2026-11-13 T123: TracingLLM spans per model call in agent_traces/; trace panel on question pages; llm.html (calls, tokens, latency p50/p95, repairs, skips, estimated cost from a dated price table)
- 2026-11-13 T122a: llm_local (Qwen2.5-1.5B GGUF via llama.cpp, JSON-schema grammar, deadlines) as llm_context on the runner CPU; real local run 0.95 in ~20 s; T122b waits for the 2026-11-14 morning run
- 2026-11-13 T121: agent_graph, a LangGraph state machine (plan, retrieve, research/tools, critique, answer) over the guarded client; 1 question per topic per day; caps test; on in morning.yml
- 2026-11-13 T120: RAG tool similar_past_questions (fastembed bge-small ONNX, cosine), only questions resolved before asof (leakage test); agent prompt v2; on in the morning workflow
- 2026-11-13 T114: ETS, SARIMAX and Chronos-Bolt tiny as local power benchmarks; one-year backtest card docs/models/power-ts.md (all three lose to the champion; Chronos best of them and beats persistence)


## Honesty audit (T171, 2026-11-13)

Every technology named on `stack.html`, `recruiters.html`, `de.html` and `README.md`,
with the code that uses it and the workflow that runs that code. Status: no open item.

| Technology | Used in | Run by |
|---|---|---|
| Python, mypy, ruff, Hypothesis, pydantic, click, Jinja2, numpy, scipy, joblib | `src/arena`, `tests` | CI `check` (`make check`) |
| DuckDB, Parquet, pandas | `analytics/sql.py` (Parquet via DuckDB `COPY`), `notebooks/explore.ipynb` | CI `check`; notebook in CI `a11y` (`make notebook`) |
| dbt (dbt-duckdb) | `analytics/dbt/` | CI `dbt` |
| scikit-learn, LightGBM, Optuna, SHAP, PyTorch | `forecasters/ml_power*.py`, `ops/explain.py` | CI `check` (requirements-ml, -torch); weekly |
| statsmodels, Chronos-Bolt | `forecasters/ts_bench.py` | CI `check` (Chronos through a fake pipeline); the real model in the committed backtest card only, labelled "backtest only" |
| MLflow, Evidently | `ops/weekly.py`, `ops/drift.py` | CI `check` (requirements-tracking); weekly |
| Claude (anthropic SDK) | `llm/anthropic_adapter.py` | CI with mocked HTTP; real calls in morning, llm-eval |
| LangGraph, fastembed (ONNX) | `agent/graph.py`, `agent/retrieval.py` | CI `check`; morning |
| llama.cpp (llama-cpp-python), Qwen GGUF | `llm/local.py` | CI with a fake backend; real runtime built in the morning workflow (first live forecasts: T122b) |
| MCP | `mcp_server.py` | CI `check` (SDK client) |
| FastAPI, uvicorn | `api/app.py` | CI `check` (TestClient); CI `docker` smoke test |
| Docker, Kubernetes (kind), Airflow | `Dockerfile`, `deploy/k8s/`, `orchestration/airflow/` | CI `docker`, `kubernetes`, `airflow` (DagBag) |
| Streamlit | `apps/dashboard/` | CI `check` (AppTest) |
| Chromium, axe (Playwright) | `tools/a11y/` | CI `a11y` |

Fixed in this audit: `stack.html` said the Parquet files were "ready for pandas, Polars,
Spark or DuckDB"; the project uses neither Polars nor Spark, so it now names only the
readers the notebook really uses.

## Moved from PROGRESS on 2026-11-19

### Done log

- 2026-11-13 T185: one-row header (7 primary links + "More" disclosure reaching Backtests, Experiments, LLM evals/observability, Data, API); rehearsal band -> pill, full sentence on Leaderboard/Findings/Methods; phone header 2 short rows; a11y 0 serious
- 2026-11-13 T184: README first screen: pitch, tour links, one image, five generated highlights (cards + evals), stack line; detail tables collapsed
- 2026-11-13 T183: repo root cleaned: requirements/ and docs/project/ (references, AGENTS.md, CLAUDE.md, scripts, Makefile, workflows, Dockerfile updated); dry runs of morning, evening, players, resolve and weekly all green
- 2026-11-13 T171: honesty audit of stack, recruiters, de and README (table in docs/project/PROGRESS.md); removed the Polars/Spark wording from stack.html; no open item
- 2026-11-13 T170: docs/interview/ (pitch EN/DE, system design, 40 Q&A, 6 STAR stories, CV/LinkedIn text); every figure checked against the generated docs/interview/numbers.md (cards, evals, live ledger via arena report cv)
- 2026-11-13 T161: players intake (form CSV -> players/B.jsonl at 09:00/09:15 UTC, random-code pseudonyms, consent, latest row before the run, never replaced); tests cover late, duplicate and invalid rows; live once H15 is done
- 2026-11-13 T160: evening job (18:00/19:30 UTC on B-1, evening.yml) publishes the next batch's questions as template v2; morning only fills missed domains (v1) and forecasts; lock unchanged; e2e covers it; Methods lists template versions
- 2026-11-13 T142: README badges, labelled demo screenshots, backtest results and skills blocks generated by scripts/readme_sections.py (checked in make check), Docker quickstart
- 2026-11-13 T141: de.html (lang="de", footer link with hreflang) and a German README section; proofreading is H17
- 2026-11-13 T140: recruiters.html (60-second summary, live counts, skill -> page -> code table tested against the repo and CI, print layout); personal section waits for H16
- 2026-11-13 T153: Airflow 3 DAGs mirroring morning/resolve/weekly (same commands, schedules, one ledger pool), DagBag check in a CI job with official constraints; T151 kind and T152 dbt jobs green in CI
- 2026-11-13 T152: dbt-duckdb project (staging, fct, marts, 21 tests) built in CI in its own venv; Data page executes the mart SQL; marts match scoring in a unit test
- 2026-11-13 T151: deploy/k8s (API Deployment+Service, CronJob) applied to a kind cluster in CI with API smoke test and one CronJob run; validated, not hosted
- 2026-11-13 T150: FastAPI read-only REST API (arena api) reusing the JSON API models and the locked DuckDB; TestClient tests; Docker image serves it in CI (curl smoke test); compose.yaml
- 2026-11-13 T143: Streamlit dashboard over the open Parquet (filters, Brier, running chart, calibration, skips), AppTest smoke test in CI, site link only when ARENA_DASHBOARD_URL is set (H19)
- 2026-11-13 T139: static JSON API api/v1/{questions,latest,leaderboard}.json with JSON Schemas generated from pydantic models, api.html, validated in tests
- 2026-11-13 T138: worked scoring example (Methods), verification walkthrough (Guide), data dictionary (Data), notebooks/explore.ipynb executed in CI on the e2e export
- 2026-11-13 T137: lock countdown, archive search, theme toggle (no storage), og:image, sticky header; app.js on every page; Playwright checks with and without JS
- 2026-11-13 T136: Experiments page adds a model timeline, tuned settings per candidate (Optuna best params now in the weekly summary) and a drift badge; test renders every view from summaries written by the real weekly job
- 2026-11-13 T135: backtests.html renders every committed model card (safe Markdown subset with tables) under a permanent BACKTEST banner; linked from Status and forecaster profiles
- 2026-11-13 T134: leaderboard skill-by-topic heatmap and head-to-head matrix (validated diverging palette, light/dark), sortable tables in app.js, Playwright sort check
- 2026-11-13 T133: topic pages (source and verified terms, kinds of question with rules, per-topic boards and race, latest questions), linked from Home; fixed unencoded question links and macro context
- 2026-11-13 T132: forecaster profile pages (what it sees, model cards, score over time vs base rate, calibration, best/worst calls, skips, LLM usage, version history) linked from the leaderboard

### Session summaries

- 2026-11-15 T193: all nine handoff repair areas implemented and pushed; 600 unit + 7 E2E
  tests, 89.39% coverage, CI/stable and live observer verified. Pages deploy/smoke succeeds;
  current-batch missing ML now surfaces as a failed health check. First real ML forecasts
  still require 16 November's unsealed batch; no old ledger bytes or official gate changed.

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

### Old "In progress" block (superseded 2026-11-19; T194 and T193e are merged and verified)

- T194: implementing the 16 November audit plan on codex/forecast-arena-repairs.
  - Numeric/SQL boundaries, participation/API states, ML provenance/graph sampling links,
    per-domain versions, promotion labels and initial recruiter/mobile improvements are local.
  - Validation in progress; do not claim the full R01–R17 plan complete or deployed.
  - Remaining: final-stage incidents, dependency triage, scheduler package, pinned eval
    comparison, prospective diagnostics/grounding, complete presentation QA and rollout.

- T193e / T057: WAIT until 2026-11-16 for the first actual pre-lock ML batch.
  - Repair code 5cfebf0 passed CI 43737672954 and promotion 43738753112; main/stable matched.
  - Observer 43739000811 passed; resolve 43739259441 deployed Pages and passed smoke.
  - Resolve health correctly fails only forecaster_coverage (today's immutable batch lacks ML).
  - Ledger verifies at 86d650a (83 files, 3 batch/day seals, 139 forecasts). Full evidence:
    `docs/project/AUDIT_REPAIR_VALIDATION.md`. Never backfill the 15 November batch.

T171 honesty-audit details are in `docs/progress-archive.md`.

## Moved from PROGRESS.md on 2026-11-23

## Previous session summary (2026-11-19)

- **State:** all agent-doable tasks are done or blocked on an owner item. `status.py`: OPEN_AGENT_TASKS=0.
  Final audit (T104): `ledger verify --git` PASS on a fresh clone (215 files, 7 batch seals, 7 day seals,
  739 forecasts); `make check` 640 unit + 7 e2e tests, `make a11y` 0 serious, site built from the real
  ledger with link check PASS; README and interview numbers regenerate clean; explainers 01-07 exist.
- **Live (verified on the ledger):** four domains, `ml` 33/33 per batch since 2026-11-16, plain, context,
  agent, agent_graph and local LLM forecasters within the caps, health green, no open incidents.
- **Waiting:** H24 (owner sets the official start 2026-11-23); T093 ensemble (built and tested, inactive until the official record starts and 300
  resolved common-set forecasts exist); T222b (SMARD publication-time measurement, 7 days);
  T092 panel (H06); T162 players (H15).
- **Open risks:** GitHub starts scheduled runs hours late (H20); `main` needs pull requests (H21); the
  SMARD day-ahead generation forecast for D+1 appears after the lock, so renewables are probably not a
  usable feature (two observations).
- **Owner items:** H24 (start the official record), H06, H15, H16, H17, H18, H19, H20.

- Audit repair T193 (2026-11-15): daily ML wiring, isolated/validated weekly evaluation,
  complete workflow readiness evidence, score/output consistency, budget accounting,
  midnight safety and executed-code provenance are implemented. Offline checks pass: 600 unit + 7 E2E tests, 89.39% coverage; lint/type checks and
  offline/live-snapshot site link checks pass. CI, isolated inference, stable promotion, workflow observer and Pages deploy/smoke are verified. T057 needs the next unsealed morning batch.
- Live snapshot (2026-11-15): 29 questions (power 6, weather 15, attention 8; markets closed
  on Sunday), no ML records in the already sealed batch. Weekly run 43695904785 published
  real power/attention champions. Both load with the repaired runtime; ledger verify --git
  passes (72 files, 3 batch seals, 3 day seals, 139 forecasts). Never backfill this batch.
- Scheduling risk (open): GitHub never started the morning slots 00:15-05:15 UTC and the
  first morning run began at 06:20; one lock-critical job still depends on GitHub's
  scheduler. Owner item H20 (external scheduler calling `workflow_dispatch`) is the real
  fix; manual deploy fallback uses `main` only after checking it equals CI-approved `stable`.
- Rehearsal start date: 2026-11-13. Official record start: not set
  (`ARENA_OFFICIAL_START_NOT_BEFORE` is 2099-12-31 until the owner picks a date, T110).
- Live site URL: https://jashd12.github.io/forecast-arena/
- Waiting on the owner: H24 (official start variable), H06, H15 (players' form and consent), H16 (recruiter page details,
  the highest-value item for interviews), H17, H18 (repo description, topics, pin), H19,
  H20 (external scheduler).


### Older done-log lines

- 2026-11-21 T258: global LightGBM backtest card: Brier 0.2079 vs 0.1930 champion (worse, interval excludes zero); stays a weekly challenger only.
- 2026-11-21 T257: conformal coverage study over 7 months (80% band: 71.0% raw to 79.4% with CQR; 90%: 80.4% to 92.5%).
- 2026-11-21 T264b: lab results in the interview numbers (generated); README lab table already generated.
- 2026-11-21 T254: docs assistant (extractive, cited, offline): 60% hits, 83% correct refusals on 26 hand-written questions; one method change after the first score is disclosed.
- 2026-11-21 T282/T283: computed rehearsal banner (streak and not-before date); README by-role guide and generated lab table.
- 2026-11-21 T277: ONNX export/serve of the LightGBM power models (`onnx_power.py`, `POST /predict/power`); HGB champion does not convert; parity 1e-4.
- T276b: experimental 80% conformal band (CQR margin from the weekly summary) in `ml` meta for power questions, shown on the question page and its coverage on Status; probability and version unchanged.
- 2026-11-21 T235: recheck of the live build; question-page chart phone layout, bars row on phones, audit tools robust to real file names
- 2026-11-21 T234: sweep of all page types at three widths; Status, tables, forest labels, index pages, tap targets fixed; layout audit extended (clipping, headings, ids, document basics)
- 2026-11-20 T233: site-wide layout system (flow spacing, cards, links, duo rows) and a layout audit in `make a11y`; no number or wording of a result changed
- 2026-11-20 T232: visual polish of the plain pages (Backtests model cards with chips, contents chips, callout banner, evals table, card spacing); no number or wording of a result changed
- 2026-11-20 T231 (PR after #19): glossary line in the home hero; "answer due Sat 21 Nov" instead of "open"; long reference pages (methods, backtests, experiments, stack) fold into sections on phones (script-driven, open without JavaScript), phone heights 2,004 to 3,165 px (were 14,000 to 20,000); browser check for the fold. H24 could not be set by the agent (variables API refused, recorded in HUMAN_TODO)

- 2026-11-19 T230: website usability pass (see TASKS): race chart, home, leaderboard, Status, archive, phone menu, chart text sizes with browser checks, contents lists. Page heights measured before and after on the real ledger; wording decision H25 and the second part (T231) are open
- 2026-11-19 T093 (prepared): owner said yes to enabling the ensemble with an official start on 2026-11-23. Only the Actions variable ARENA_OFFICIAL_START_NOT_BEFORE needs the owner (H24); the ensemble registers itself after 60 official common-set questions (expected 2026-11-30). Added a test that the switch works on a real ledger folder. #16 and #17 merged
- 2026-11-19 T223b (agent): llm-eval run 44611596780 (12 golden questions, plain/context/agent, cap 200,000 tokens, owner-approved H23) completed with no skips: Brier 0.2255 / 0.1923 / 0.2056; no paired difference is supported, the agent is not better than context here (evaluation set, small, not live). Result committed; numbers.md regenerated
- 2026-11-19 T090, T093, T222b, T223b, T104: ensemble built and tested (inactive until the official record starts and 300 resolved common-set forecasts exist; T093 waits); SMARD forecast-publication probe after the morning and evening jobs; `--variant agent` in the eval harness and workflow (the paid run waits for H23); final audit passed on a fresh ledger clone
- 2026-11-19 T047, T058, T069: explainers 03 (question design and baselines), 04 (ML models, leakage, calibration, promotion) and 05 (LLM forecasters and agent) written from the code, each with ten interview questions; T065 and T068 ticked from the ledger (plain, context, agent and agent_graph forecast daily within the caps). Next ready: T090 ensemble
- 2026-11-19 T223b (plain vs context): llm-eval run 44592033036 (24 golden questions, cap 100,000 tokens, owner-approved H22) completed with no skips: Brier 0.3483 plain vs 0.1855 context, paired difference +0.1628 [+0.0603, +0.2679] (evaluation set, not live). Result committed; numbers.md regenerated. Agent variants in the harness remain open
- 2026-11-19 T223a: dispatched llm-eval from main (24 questions, 60,000-token cap, run 44586958389): plain answered everything, context hit the cap (budget_exhausted skips), so the run is not committed. T223 split; T223b needs the owner's decision on a higher eval token cap (H22). All of PRs #5-#12 are merged
- 2026-11-19 T224: 90-second EN/DE walkthrough (one batch from question to score) added to docs/interview/pitch.md, no figures; the owner has to rehearse it
- 2026-11-19 T222a: checked the audit's SMARD forecast-vintage premise before building it. Terms (CC BY 4.0, HEDWIG review) and forecast series ids recorded; one live observation shows D+1 forecasts not yet published at 16:06 UTC on D, so they probably cannot be used at the 09:30 UTC lock. Archive not built; T222b measures publication time over 7 days. T223 now depends on T222a
- 2026-11-19 T220: backtest slice card (`docs/models/power-slices.md`, shown on the Backtests page): ml vs persistence by template, month and target-day type with paired day-block intervals and a generated statement of where persistence is not worse (evening_gt, holidays and several single months: no supported difference); negative-price days not covered (DECISIONS)
- 2026-11-19 T214, T221: the social preview image (1200x630) and og/twitter meta already existed; now tested, and H18 says where to upload it. Methods explains why a base rate can score above 0.25 early (audit F9)
- 2026-11-19 T212-T213: README opens with the question, a generated "Result so far" block (backtest figures, ml-vs-persistence interval, the 365-independent-days caveat, live status), links and screenshot; stack in a details block. `scripts/screenshots.py LEDGER_DIR` rebuilds docs/img/home.png from a real ledger (dated caption). Also fixed my T210 hero: it cited the ml-vs-base-rate interval for a claim about persistence; it now uses the card's `ml - persistence` row
- 2026-11-19 T210-T211: recruiter first screen (kicker, honest H1, result line copied from the model card, buttons; owner facts from optional `site_content/recruiter_facts.json`, omitted when absent) and three role cards with deep links, tested; verified above the fold at 1366x768 and 390x844 on a build from the real ledger
- 2026-11-19 T204-T206: RUNBOOK schedule table now matches the gated hourly crons and documents GitHub's late starts; H20 has exact dispatch steps for morning, evening and players; Status and Play say whether the players' intake works (from run manifests); `api/v1/leaderboard.json` has a `common` block equal to the home board (rows of the all-questions board stay as before)
- 2026-11-19 T200-T203 (audit plan docs/project/AUDIT_2026-11-19.md): official-start wording names the not-before rule; home standings show questions and days; placeholder sentence removed from the recruiter page (test over all built pages); leaderboard overflow fixed (sr-only spans escaped the scroll container) with a page-width check in `make a11y`. T057 and T193e ticked from the ledger (ml 33/33 each batch 11-16 to 11-19)
- 2026-11-15 T193a-d: implemented handoff F1-F9; 600 unit and 7 E2E tests pass, 89.39% coverage; isolated HGB/LightGBM/PyTorch inference CI job; real read-only GitHub audit finds 17 attempts and fails closed on old missing evidence; current ledger and champion loading verified
- 2026-11-14 T182: scripts/smoke_site.py (pages, data files, referenced assets, CSP meta, build age under 26 h) runs after every Pages deploy in morning/evening/resolve; green on a real resolve deploy; `make smoke-site` for manual runs
- 2026-11-14 T046 (code): weather, attention and markets on by default in morning/evening/resolve, four-domain e2e test; WAIT until the first real evening run publishes them (check set for 16:40 UTC). Lesson: a `#` comment inside `${{ }}` broke all dispatches for ~30 min; tests/unit/test_workflows_syntax.py now guards it
- 2026-11-14 T034, T122b, T180, T181: checked on the ledger. Batch 2026-11-14 was sealed at 06:24 UTC by a SCHEDULED morning run (first one to start: 06:20, six hours after the 00:15 slot; slots 00:15-05:15 never ran; the gate made the later ones no-ops); questions all `-v2`; 2026-11-13 fully resolved and day-sealed; `agent` 3 forecasts (thinking-block fix works), `llm_local` 3 forecasts (open model live), `agent_graph` 1 error skip = a real bug (plan-step tool calls not answered), fixed with a regression test; `ledger verify --git` PASS
- 2026-11-14 T190: both contracts compared on the golden set (evals/results/eval-20261114T0052-*): structured outputs not better (83% first-try valid JSON for llm_context), caching raised one-shot cost; both off live; schema sent to the API stripped of unsupported keywords; metric bugs fixed
- 2026-11-14 T192: Status page "When the scheduled jobs actually started" (first real run per job per day vs the first slot)
- 2026-11-14 T191: OTLP/JSON export of the LLM spans (data/otlp/, linked from LLM observability) and a Polars-vs-DuckDB check in the executed notebook; polars pinned in requirements/nb.txt; named on stack and recruiter pages only now
- 2026-11-13 T189: Experiments shows the labelled challenger backtests (parsed from the cards) until the first live weekly run; home KPI "days replayed in the backtests" while one topic is live; "How the AI agent worked" card from real successful traces only; a11y 0 serious
- 2026-11-13 T188: CI coverage floor 87% (CI measures 88.95%); coverage and test-count badges in the README from docs/badges/*.json, checked in CI by scripts/badges.py --check so they never overstate
- 2026-11-13 T187: docs/CODE_TOUR.md; all 218 `# fmt: skip` removed (ruff format); site/build.py split into content.py + shaping.py (877 -> 474 lines); cli.py -> cli/ package (record, jobs, reports, llm_cmds; 28 commands kept); e2e site byte-identical except data.html, where SQL tie-breakers fixed a real nondeterminism
- 2026-11-13 T186: home hero: "joining soon" gone; labelled BACKTEST card (one year of electricity, parsed from docs/models/power.md) beside live standings; recruiter page: honest authorship line, "five things worth 30 seconds" (figures from eval files); README screenshots regenerated

