# docs/project/PROGRESS.md - state between sessions

The agent keeps this file current. Newest information first. Keep it under 120 lines;
move older "Done log" lines to `docs/progress-archive.md`.

## Now

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
- Waiting on the owner: H06, H15 (players' form and consent), H16 (recruiter page details,
  the highest-value item for interviews), H17, H18 (repo description, topics, pin), H19,
  H20 (external scheduler).

## In progress

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

## Session summaries

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
