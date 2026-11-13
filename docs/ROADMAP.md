# Forecast Arena: roadmap to win Werkstudent AI/ML/DS interviews in Germany (v2)

## Context

Jashdeep (MSc student in Gießen, English-speaking) wants Forecast Arena to get him
working-student (Werkstudent) AI/ML/DS interviews in Germany. The repo (commit `78c01d4`,
70 tasks done) has a rigorous pipeline, but the live record is still empty (first morning
run 2026-11-13 05:30 UTC), only power + baselines + LLMs are wired live, and several skills
that postings ask for are missing or not visible.

What current German postings ask for (searched 2026-11-12):
- **AI-engineer working students:** a self-built **LangChain/LangGraph** project with code,
  Python + REST APIs + SQL, RAG and vector stores, LLM **tracing and evals**, MCP, agents
  ([Thorit](https://freehire.me/jobs/working-student-ai-software-engineer-langchain-all-genders-thorit-yr6ih5md),
  [AgentixLake](https://join.com/companies/dataventio/16894208-working-student-ai-engineer-llms-rag-and-ai-agents),
  [appliedAI](https://www.appliedai.de/en/company/career/working-student-m-f-x-ai-engineering-product-development/),
  [SAP AI Engineer](https://jobs.sap.com/en/jobs/744000156366769/ai-engineer-fmd/)).
- **ML/DS working students:** Python, SQL, pandas/Polars, scikit-learn, PyTorch or
  TensorFlow, Git, Docker, CI/CD, MLflow
  ([Glassdoor listing](https://www.glassdoor.com/Job/werkstudent-machine-learning-jobs-SRCH_IC2813070_KO0,28.htm),
  [Jooble listing](https://de.jooble.org/stellenangebote-working-student-machine-learning/K%C3%B6ln)).
- **Data/analytics working students:** SQL + Python, **dbt**, **Airflow**, dashboards
  (Power BI/Tableau), Snowflake/Databricks as a plus
  ([Pergolux](https://www.arbeitnow.com/jobs/companies/pergolux/working-student-analytics-engineer-berlin-127740),
  [aijobs.net listings](https://aijobs.net/job/werkstudent-data-engineer-mwd-munchen-bayern-deutschland-285815/)).

Owner decisions (2026-11-12/13; record in `DECISIONS.md`, tick matching `HUMAN_TODO.md`
items): self-hosted JavaScript allowed; add RAG, PyTorch, LightGBM + Optuna + SHAP,
conformal + ensemble; German page, recruiter page, Streamlit dashboard, players'
leaderboard; "more advanced" additions below.

Hard constraints (unchanged): `AGENTS.md` protocol and integrity rules I1-I8; **zero extra
cost** (Claude Haiku 5.5 under the 150k tokens/day cap; everything else on free GitHub
Actions/Pages; no paid cloud, no free tiers that need a credit card); **never list a
technology the project does not really use** (I5): each addition must run, be tested, and
report its measured result even when it loses; no accounts, secrets, repo settings or legal
text by the agent; never work around a permission refusal; dispatch workflows from `main`;
wait for CI + `promote` before the next push.

## Priorities (do in this order; stop a tier only when its checks pass)

| Tier | What | Why it matters to a hiring manager |
|---|---|---|
| 1 | Phase 0-1: live core complete | Real, growing data; nothing else matters on an empty site |
| 2 | Phase 2A-2B: ML challengers, RAG, LangGraph agent, evals + tracing | The most requested AI-engineer and ML keywords, each with a measured result |
| 3 | Phase 3: website depth + interactivity | Keeps a visitor exploring |
| 4 | Phase 4: recruiter page, German page, README, dashboard | Converts a visit into an interview |
| 5 | Phase 5: FastAPI + Docker + MCP + dbt + orchestration | Engineering breadth |
| 6 | Phase 6: players' leaderboard; Phase 7: interview kit | Engagement and interview performance |

## Phase 0 - Bookkeeping

- Add this roadmap to `TASKS.md` as "Phase 10 - Portfolio roadmap" (`T110...`, existing
  line format with deps / Do / Done when) so `scripts/status.py` drives it.
- `DECISIONS.md`: "Portfolio roadmap (owner approved)"; supersedes the 2026-11-12 entries
  that rejected PyTorch/SHAP/JavaScript. `docs/SPEC.md`: amend section 8 (challengers, new
  forecasters, RAG tool, players) and section 11 (self-hosted JS, no storage, no
  third-party requests).
- **T110 Official-start gate:** when building T035 add `ARENA_OFFICIAL_START_NOT_BEFORE`.
  The official record must not start until Phases 1-2 and the Phase 6 timing change are
  live (keeps it free of version churn). The 5-clean-days rule stays.
- Heavy dependencies: one optional file per extra (`requirements-ml.txt`,
  `requirements-llm.txt`, `requirements-api.txt`, ...), separate cached CI jobs, unit tests
  with tiny data, fakes and `pytest.importorskip`. Core `make check` stays fast and offline.

## Phase 1 - Finish the live core (existing tasks)

T032 (verify the first real batch), T033, T034, T035 (+T110), T036, T046 (weather,
attention, markets live), T057 (wire `ml` in `src/arena/ops/wiring.py::build_forecasters`:
registry models for power/attention, `WeatherRules`, `MarketsModel`, `CryptoModel`), T065,
T068, T080, explainers T047/T058/T069/T085. Crypto (T045e) stays blocked on H12.

## Phase 2A - Classical and deep ML (measured challengers)

Pattern: model in `src/arena/forecasters/`, trainer in `wiring.py::weekly_setup`, evaluated
by `src/arena/backtest/harness.py` + `report.py` (bootstrap CIs and Diebold-Mariano already
there), stored via `forecasters/registry.py`, model card via `backtest/cards.py`.

- **T111 Multi-candidate weekly promotion:** generalise `src/arena/ops/weekly.py` to several
  candidates per domain; promote the best only if not worse than the champion; summary lists
  every candidate. Experiments page shows the champion/challenger table.
- **T112 LightGBM + Optuna + SHAP** (power, attention): same features (`ml_power.features`,
  `ml_attention.features`); Optuna (fixed seed, ~30 trials, time-series CV with gap); SHAP
  TreeExplainer summary next to the permutation importance in `src/arena/ops/explain.py`.
- **T113 PyTorch quantile network** (power): small MLP/TCN, pinball loss, CPU wheel,
  deterministic seeds.
- **T114 Time-series foundation model** (power): zero-shot quantile forecasts from a tiny
  pretrained model (e.g. Chronos-Bolt tiny, CPU) as a challenger; weights cached with
  `actions/cache`. Classical benchmark too: `statsmodels` SARIMAX/ETS in the backtest table.
- **T115 Conformal prediction:** conformalized quantile regression (rolling split-conformal)
  for the power quantiles; coverage before/after beside `power_quantile_diagnostics`.
- **T116 Ensemble** (existing T090/T093): stacking logistic regression per SPEC 8.6; site
  shows "waiting: n/300" until active.
- **T117 Power analysis for the research question:** from the observed variance of daily
  paired Brier differences, compute how many official days are needed to detect a given
  difference at 80% power; show on Findings ("about N more days to resolve H1").
- **T118 Quality:** Hypothesis property tests (ledger canonical JSON, hash chain, scoring
  bounds); `pytest-cov` figure in the CI summary; pandera schemas for source responses.

## Phase 2B - LLM engineering (the AI-engineer keywords)

- **T120 RAG tool:** `similar_past_questions` in `src/arena/agent/tools.py`: local ONNX
  embeddings (`fastembed`, no API cost), vector search over **resolved** questions with
  resolve time < asof only (I3), returns top-k titles, outcomes, base rate. Index stored as
  Parquet/DuckDB in `data_cache/`; fake embedder in tests; new prompt version
  `agent_system_v2` (visible in the changelog).
- **T121 LangGraph agent** (`agent_graph` forecaster): a LangGraph state machine
  (plan -> retrieve (T120) -> tools -> self-critique -> answer) through `langchain-anthropic`,
  wrapped by the existing `GuardedLLM`/`BudgetGuard` (`src/arena/llm/budget.py`) so the
  caps hold; 1 sampled question per domain per day. Research angle: framework agent vs the
  hand-written loop in `src/arena/agent/forecaster.py`, same model, same tools.
- **T122 Open-source local LLM** (`llm_local` forecaster): a small quantized open model
  (GGUF via `llama-cpp-python`, about 1 GB, cached) on the GitHub runner CPU, same prompts
  and JSON contract as `llm_context`, strict time limit, skips recorded on timeout. Zero API
  cost; gives "open model vs Claude Haiku" on the leaderboard.
- **T123 LLM tracing:** OpenTelemetry-style spans (prompt version, model, tokens, latency,
  tool calls, parse/repair outcome) written with each forecast to `agent_traces/`; a
  trace viewer on the question page and an **LLM observability page** (requests, tokens,
  estimated cost per day from a dated price table, parse-failure and skip rates).
- **T124 LLM eval harness:** `arena eval run` + manual workflow `llm-eval.yml`: a frozen
  golden set of resolved questions (after the model's training cutoff), prompt variants
  A/B, metrics (Brier, log score, calibration, JSON validity, repair rate, cost per
  forecast), regression gate with FakeLLM in CI, real runs only by manual dispatch within
  the daily cap. Results page "LLM evals", labelled as evaluation, never mixed into live
  scores (I4).
- **T125 MCP server:** `arena mcp` (stdio, official `mcp` Python SDK) exposing read-only
  tools over the ledger/DuckDB (`list_questions`, `get_question`, `leaderboard`,
  `run_sql` with a read-only allowlist). Tested in CI with the SDK's client; documented in
  the README ("connect Claude Desktop/Code to the benchmark").

## Phase 3 - Website: every page worth exploring

Shared: one self-hosted `src/arena/site/static/app.js` (vanilla, progressive enhancement,
no storage, same-origin JSON only), CSP `<meta>` `default-src 'self'`; replace the
"no script" test in `tests/unit/test_site_pages.py` with "scripts only from `static/`, no
inline handlers, no third-party URLs"; update `docs/COMPLIANCE.md` and the Privacy template.
Reuse `site/charts.py` (`race_svg`, `forest_svg`, `series_class`, validated palette),
`macros.html` (`page_head`, `board_table`), `site/titles.py`, `analytics/sql.py`. Every
chart keeps a table view; `make a11y` stays at 0 serious/critical.

- **T130 "Can you beat the AI?"** (`play.html` + Home teaser): build writes `data/game.json`
  (resolved questions with every forecaster's probability); slider, reveal, own Brier vs
  each forecaster, session score in memory only.
- **T131 Question page:** chart of the underlying series from `snapshots/<domain>/...` with
  threshold and observed value; agent trace panel (T123); retrieved similar questions
  (T120); previous/next links.
- **T132 Forecaster profiles** (`forecasters/<id>.html`): what it sees, model card, version
  history (`version_changelog`), score over time, calibration, best/worst calls, cost.
- **T133 Topic pages** (`topics/<domain>.html`): source, licence, question types in plain
  words, per-topic leaderboard and race, recent questions.
- **T134 Leaderboard:** forecaster x topic heatmap (Brier skill vs base rate), head-to-head
  matrix with intervals, sortable tables, topic tabs, cost-vs-accuracy scatter for LLMs.
- **T135 Backtests page:** render generated model cards (`docs/models/*.md`; e.g. power ML
  0.193 vs base rate 0.247) under a permanent "BACKTEST - not the live record" banner (I4).
- **T136 Experiments:** champion/challenger table, Optuna summary, SHAP + permutation bars,
  conformal coverage, drift badges, model timeline.
- **T137 Home/global:** countdown to the lock, latest-results strip, archive search/filter
  (`data/questions.json`), theme toggle without storage, `og:image`, sticky nav.
- **T138 Methods/Guide/Data:** worked scoring example, leakage diagram, verification
  walkthrough, data dictionary, executed notebook `notebooks/explore.ipynb` (pandas, Polars,
  DuckDB on the open Parquet).
- **T139 Static JSON API:** `api/v1/{leaderboard,questions,latest}.json` + schema page.

## Phase 4 - Recruiter-facing

- **T140 "For recruiters"** (`recruiters.html`, hero + nav): 60-second summary, measured
  results, table mapping posting requirements (Python, SQL, scikit-learn, LightGBM,
  PyTorch, LangGraph, RAG, evals/tracing, MCP, MLflow, Docker, CI/CD, dbt, statistics) to
  the page and source file that proves each; print one-pager. Personal lines from
  `site_content/recruiters.md` (reuse the `[FILL IN` guard in `build.py::read_content`).
- **T141 German summary** (`de.html`, `lang="de"`, "Auf Deutsch" link) + README section.
- **T142 README overhaul:** badges, screenshots, generated results table
  (`arena report cv`), architecture, skills list, quickstart with Docker.
- **T143 Streamlit dashboard:** `apps/dashboard/streamlit_app.py` on the public Parquet
  (filters, calibration, scores); CI smoke test with `AppTest`; linked from the site only
  when `ARENA_DASHBOARD_URL` is set.

## Phase 5 - Engineering breadth

- **T150 FastAPI service:** `src/arena/api/` read-only REST API over DuckDB (questions,
  forecasts, leaderboard, OpenAPI docs), pydantic response models, tests with `TestClient`;
  added to the Docker image (`Dockerfile` exists) with a `docker compose` file.
- **T151 Kubernetes check in CI:** job creates a `kind` cluster on the runner, applies
  `deploy/k8s/` (Deployment + Service + CronJob for the jobs), smoke-tests the API. Labelled
  honestly on the site: "validated in CI, not hosted".
- **T152 dbt:** `analytics/dbt/` project with `dbt-duckdb`: staging models over the Parquet
  export, marts (daily scores, forecaster x topic), dbt tests (unique, not null, accepted
  values) run in CI; the Open data & SQL page reads the marts.
- **T153 Orchestration DAG:** `orchestration/airflow/arena_dag.py` mirroring morning ->
  lock -> resolve -> weekly; validated in CI by importing it with Airflow's `DagBag`.
  Stated plainly: production scheduling is GitHub Actions.

## Phase 6 - Public players' leaderboard

- **T160** Timing change: questions published about 18:00 UTC on B-1 so every time zone can
  play before the 09:30 UTC lock; machine forecasters still run in the morning; changed
  templates get `template_version` 2; before the official start (T110).
- **T161** Intake: extend `src/arena/forecasters/panel.py` (CSV adapter, lateness rule
  exist) to per-player forecasts under random ids; pre-lock run about 09:00 UTC; latest
  valid answer per nickname and question; minimum answers before ranking.
- **T162** Site: players' leaderboard on the same questions and scoring; Play page with the
  form link, rules, consent summary.

## Phase 7 - Interview kit (docs only)

- **T170** `docs/interview/`: 2-minute pitch (English and German), system-design
  walkthrough, 40 likely questions with honest answers (leakage, calibration, why boosting
  beat or lost to the network, RAG design, eval design, cost control), STAR stories from
  real incidents in `PROGRESS.md`, CV bullets and LinkedIn project text (from
  `arena report cv`), a blog-post draft for the owner to publish.

## Human items to add to HUMAN_TODO.md

Personal details for the recruiter page (degree, university, availability, LinkedIn);
German proofreading; repo description, topics and pinning; Streamlit Community Cloud deploy
and `ARENA_DASHBOARD_URL`; Google Form + consent text + privacy update for players; approval
line in `CLAUDE.md` if a workflow should publish the Docker image to GHCR (optional);
existing H12 (CoinGecko) and H14 (street address).

## Verification

- Each task: its "Done when", `make check` (ruff, mypy, unit tests, offline e2e),
  `make site-e2e` + `make a11y`, push, green CI and `promote`.
- Extras: each optional CI job green (ml, llm, api/kind, dbt, airflow, dashboard).
- Live: dry-run dispatch first, then real; `arena --ledger-dir _ledger ledger verify --git`
  on a fresh clone of the `ledger` branch.
- Site: Playwright screenshots (desktop light, phone dark); pages work with JavaScript off;
  a Playwright check asserts no request leaves the origin; link check passes.
- Models: a committed model card per challenger; weekly dry run prints the candidate table.
- LLM: Status/LLM page shows daily tokens under 150k with `agent_graph` and evals included;
  `llm_local` adds no API cost; no new secrets.
- Honesty audit before finishing: every technology named on `stack.html`,
  `recruiters.html`, `de.html` and the README is imported by code that CI runs.
- Done when `python scripts/status.py` prints `OPEN_AGENT_TASKS=0` and the three goal
  commands of the original brief pass.
