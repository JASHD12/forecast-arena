# PROGRESS.md - state between sessions

The agent keeps this file current. Newest information first. Keep it under 120 lines;
move older "Done log" lines to `docs/progress-archive.md`.

## Now

- Phase: 2 go-live. Actions (H10) and Pages (H03) are fixed by the owner; CI, promote,
  morning/resolve/weekly dry runs are green. T032 waits for the first scheduled real
  morning run (2026-11-13 05:30 UTC). Still waiting on the owner: H04, H06, H11.
- Rehearsal start date: (not yet live)
- Official record start date: (not yet set, see SPEC 2.9)
- Live site URL: (not yet deployed)

## In progress


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

- 2026-11-13 T125: arena mcp, read-only MCP server (official SDK 2.3.0): list_questions, get_question, leaderboard, run_sql (single SELECT, DuckDB external access off); stdio test; README setup
- 2026-11-13 T124 follow-up: first real evals showed 400-token cap truncating thinking answers; cap now from settings (workflow default 1024) and in every LLM version string
- 2026-11-13 T124: eval harness (frozen golden set of 186 past power questions, llm_plain vs llm_context A/B, Brier/log/ECE/skill/JSON validity/repairs/cost), FakeLLM CI gate, manual llm-eval.yml, evals.html (EVALUATION banner)
- 2026-11-13 T123: TracingLLM spans per model call in agent_traces/; trace panel on question pages; llm.html (calls, tokens, latency p50/p95, repairs, skips, estimated cost from a dated price table)
- 2026-11-13 T122a: llm_local (Qwen2.5-1.5B GGUF via llama.cpp, JSON-schema grammar, deadlines) as llm_context on the runner CPU; real local run 0.95 in ~20 s; T122b waits for the 2026-11-14 morning run
- 2026-11-13 T121: agent_graph, a LangGraph state machine (plan, retrieve, research/tools, critique, answer) over the guarded client; 1 question per topic per day; caps test; on in morning.yml
- 2026-11-13 T120: RAG tool similar_past_questions (fastembed bge-small ONNX, cosine), only questions resolved before asof (leakage test); agent prompt v2; on in the morning workflow
- 2026-11-13 T114: ETS, SARIMAX and Chronos-Bolt tiny as local power benchmarks; one-year backtest card docs/models/power-ts.md (all three lose to the champion; Chronos best of them and beats persistence)
- 2026-11-13 T085: explainer 07 (operations and monitoring) with real incidents
- 2026-11-13 T080: Status page adds missed days, source freshness (latest batch/answer, overdue), LLM usage per day vs cap, LLM parse-failure rates; e2e now records usage like the CLI
- 2026-11-13 T036: explainers 01 (ledger, forecast before truth) and 02 (power questions), ten Q&A each
- 2026-11-13 T035+T110: clean-day streak from run manifests, recorded health reports and day seals; official start written once (write_raw refuses a second write); not-before gate (default 2099-12-31 until roadmap changes are live); streak on Status
- 2026-11-13 T033: health checks + incident issue live-tested: failing dry run 43396287940 opened issue #1, healthy dry run 43397819217 closed it
- 2026-11-13 T118: Hypothesis property tests (round-trip, scoring bounds, any changed byte detected, late forecasts rejected) found a real bug: verify crashed on non-UTF-8 bytes -> now a LedgerError; pytest-cov in CI summary (87% coverage)
- 2026-11-13 T117: power analysis (days needed to detect a 0.01/0.02 Brier gap at 80% power) on Findings
- 2026-11-13 T113: PyTorch quantile MLP ties the champion in the 1-year power backtest (0.1927 vs 0.1930, diff -0.0003 [-0.0087, +0.0081], DM p=0.95): published honestly in docs/models/power-mlp.md
- 2026-11-13 T115: conformalized quantile regression (CQR) for the power 80/90% bands in the weekly job and on Experiments; synthetic test restores 38% -> ~80% coverage
- 2026-11-13 T112: LightGBM + Optuna challenger beats the champion in the 1-year power backtest (Brier 0.1884 vs 0.1930, diff -0.0045 [-0.0069, -0.0021], DM p<0.001); card docs/models/power-lgbm.md
- 2026-11-13 T032: first real batch (6 power questions, 18 forecasts incl. Claude Haiku 5.5) on the ledger at 08:27 UTC, before the 09:30 lock; verify --git PASS; rehearsal start 2026-11-13. Both morning schedules were skipped by GitHub; dispatched by hand from `stable` (run 43393206918)
- 2026-11-13 fix: agent repair step re-sent the model's reply (two assistant turns in a row -> API 400 on thinking blocks); regression test; workflows default ARENA_LLM_EFFORT=low so thinking does not use the 400-token answer budget
- 2026-11-13 T111: weekly job trains several candidate families per domain, promotes the best only if not worse than the champion; candidates table on Experiments
- 2026-11-13 Phase 0: roadmap tasks T110-T171 in TASKS.md, H15-H19, decisions, SPEC 8.8/11 amendments; scheduled resume every 5 h (trig_016b95iyHSuR6B44xPaAgDPF)
- 2026-11-13 owner approved docs/ROADMAP.md (portfolio roadmap v2); next session starts with its Phase 0 (add tasks T110+ to TASKS.md), then Phase 1
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
