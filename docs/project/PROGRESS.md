# docs/project/PROGRESS.md - state between sessions

The agent keeps this file current. Newest information first. Keep it under 120 lines;
move older "Done log" lines to `docs/progress-archive.md`.

## Now

- Phase 10 (portfolio roadmap) done: `status.py` prints OPEN_AGENT_TASKS=0. Still to
  check on 2026-11-14 (WAIT): T122b (`llm_local` live forecasts) and T034, plus that the
  `agent` answers again after the adapter fix. Waiting on the owner: H06, H15 (and the
  optional H16, H17, H19).
- Rehearsal start date: 2026-11-13 (first real morning run; 6 power questions, resolved).
- Official record start date: not set; `ARENA_OFFICIAL_START_NOT_BEFORE` is 2099-12-31
  until the owner chooses a date (T110).
- Live site URL: https://jashd12.github.io/forecast-arena/

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

## In progress


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

## Open risks and surprises

- **2026-11-13 live agent failed on its 3 sampled questions** (HTTP 400: replayed
  thinking blocks "cannot be modified"; the adapter dropped null fields). Fixed with a
  regression test (docs/project/DECISIONS.md); the skips stay recorded. Verify on 2026-11-14. Scheduled
  resolve runs start hours late; a real resolve was dispatched at about 16:40 UTC.
- Shared sandbox IPs are rate-limited: Open-Meteo (daily quota exhausted, hence Bright
  Sky), GDELT (HTTP 429), Wikimedia (429 with short Retry-After). GitHub runners also
  share IPs; the live jobs record failures as skips or tool errors, never guesses.
- SMARD says the licensing of wholesale prices is under review (HEDWIG procedure): re-check
  https://www.smard.de/home/datennutzung monthly.
- Wikimedia pageview licence not verified (docs page is JavaScript-only); the site names
  the source without claiming a licence.
- The batch seal timing excludes a same-day human panel (proposal in docs/project/DECISIONS.md);
  public players now have their own pre-lock file (T161).
- This session's network environment is the personal environment `forecast-arena`
  (created in this session with the data-source hosts); Default was not changed.
- MLflow printed a hint telling the reader to load a bundled "skill"; treated as tool
  output, not acted on (S11).

## Done log

- 2026-11-13 T184: README first screen: pitch, tour links, one image, five generated highlights (cards + evals), stack line; detail tables collapsed
- 2026-11-13 T183: repo root cleaned: requirements/ and docs/project/ (references, AGENTS.md, CLAUDE.md, scripts, Makefile, workflows, Dockerfile updated)
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
