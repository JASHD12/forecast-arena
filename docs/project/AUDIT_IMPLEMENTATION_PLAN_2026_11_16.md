# Forecast Arena: audit and implementation handoff

Reviewed 15–16 November 2026, Europe/Berlin. This is an **audit and plan**; no repair code, workflow dispatch, issue update, deployment, repository setting change or live-ledger write was performed during this review.

Repository: [JASHD12/forecast-arena](https://github.com/JASHD12/forecast-arena). Website: [Forecast Arena](https://jashd12.github.io/forecast-arena/). Source inspected: [`b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa`](https://github.com/JASHD12/forecast-arena/tree/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa), with `main` and `stable` equal. Detailed forecast inspection uses immutable ledger [`958194904fce6c50b5f0b5a1513af3853dcb645e`](https://github.com/JASHD12/forecast-arena/tree/958194904fce6c50b5f0b5a1513af3853dcb645e); subsequent observer-only heads `3413c337409d908299118005a341bee60e0e0423` and `e66f87841404b2e612f9d307c0596d2f4780aa6e` were identified remotely. Live pages inspected include the build dated **16 November 06:57 UTC**. The successful deployment workflow identifies source `b072b2d`; the HTML does not itself expose a code/ledger SHA, so this association comes from workflow evidence.

**Final refresh, 16 November 13:09 UTC (14:09 Berlin):** source refs remain unchanged; the public API is still generated at 06:57 UTC, with 33 ML forecasts and 0 resolved. The reported power question is now past its 12:30 UTC resolution-availability threshold, but the latest completed resolve workflow remains 06:57 UTC. No later resolution run was visible in the recent API history. This is a pending collection/publication check; it does not establish an ML-inference failure or a source outage. The latest observer 43868561359 succeeded.

Supporting evidence is saved beside this document in `forecast-arena-audit-evidence-2026-11-16/`; this document contains the implementation requirements and does not depend on those files to explain its findings.

Quick navigation: [reported ML/LangGraph cases](#b1-the-two-reported-pages) · [findings R01–R17](#c-findings-and-required-resolutions) · [job research](#d-german-working-student-job-evidence) · [hiring copy](#e-hiring-presentation-and-disciplined-stack-plan) · [ordered backlog](#f-ordered-implementation-backlog-and-ownership) · [agent assignment](#i-copy-paste-implementation-assignment).

## A. Executive assessment

The core forecasting system works through live inference and publication. It also has important remaining correctness, operational-monitoring and presentation gaps. The original missing daily ML integration has been repaired and has now passed its first real morning acceptance: **33 ML forecasts for 33 questions**, across electricity, weather, Wikipedia attention and currencies. The new batch was sealed at **06:43:23 UTC on 16 November**, before its **09:30 UTC** lock. [Morning run](https://github.com/JASHD12/forecast-arena/actions/runs/43816839671), [batch seal](https://github.com/JASHD12/forecast-arena/blob/958194904fce6c50b5f0b5a1513af3853dcb645e/chain/batch/2026-11-16.json).

The user-reported missing ML leaderboard row currently means **no resolved ML forecasts yet**, rather than failed ML inference. LangGraph also works: it published four forecasts in the new batch, one per topic, and recorded 29 intentional `not_sampled` skips. The site makes these distinctions too difficult to discover.

The five highest-impact actions are:

1. **R01/R02: close two reproduced correctness holes.** Invalid source numbers can become a scored NO with a NaN observation; the read-only SQL interface accepts a CTE-prefixed DELETE against its in-memory tables.
2. **R03/R04: make every forecaster's participation and explanation visible.** Show ML as awaiting resolution; explain LangGraph sampling on the question itself; add honest ML method/provenance evidence instead of inventing an LLM rationale.
3. **R07–R09: finish operational reliability.** Reconcile incidents against final workflow/deployment outcomes, triage vulnerable dependency pins, and prepare the existing owner-controlled scheduler task.
4. **R12–R14: build a convincing hiring entry point.** Put candidate name, target role, one verified result and two useful actions in the first screen; expose the recruiter route on mobile; populate GitHub's empty About metadata.
5. **R05/R06/R11/R15: remove contradictory status and evidence claims.** Show all four live ML versions, correct promotion labels, refresh schedule/status documentation and pin comparable LLM evaluation evidence.

Existing strengths: time-aware data access; explicit skips; append-only records and public pre-lock commits; baselines; proper scores and uncertainty; published losing challengers; separate backtest and live results; fresh-process model-loading tests; typed Python; substantial CI coverage; a small self-hosted frontend. Preserve these.

Important limits: the official evaluation has not begun; the new ML batch has not resolved in the inspected snapshot; a later real champion replacement is still a future acceptance check; some optional features need owner configuration; candidate education, languages, availability and personal contribution are unverified. A bundled request for those details was sent during the review; do not fill missing answers from assumptions.

## B. Verified behavior and coverage

### B1. The two reported pages

On [the evening-price question](https://jashd12.github.io/forecast-arena/questions/power-evening_gt-DE_LU-2026-11-17-v2.html):

| Forecaster | Published P(YES), rounded on site | What absence elsewhere means |
|---|---:|---|
| ML | 19% (`0.19214962868834604`) | Forecast exists; no scored result until the question resolves. Model `power-gbq-r1-2026-11-12`. |
| LangGraph | No forecast | Explicit `not_sampled`, rather than a tool/model error. Its electricity sample is the **mean-price** question in this batch. |
| Agent with tools | 35% | Published summary and trace present. |
| LLM context | 30% | Published summary and trace present. |
| Local LLM | 55% | Published summary and trace present; its text is a model assertion, not resolution evidence. |
| LLM plain | 12% | Published summary and trace present. |
| Base rate / persistence | 64% / 38% | Baselines do not produce LLM reasoning. |

The ML forecast and LangGraph skip are [forecast lines 35 and 40](https://github.com/JASHD12/forecast-arena/blob/958194904fce6c50b5f0b5a1513af3853dcb645e/forecasts/2026/11/16.jsonl#L35). ML currently stores a model hash and artifact SHA, not per-question explanation text. `question.html` renders “Reasoning” only for nonempty `Forecast.rationale`, and renders “How the AI forecasters worked” from LLM traces only. Therefore ML's absence from those sections follows the current data contract, although the product needs a better explanation experience. [Template](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/site/templates/question.html#L40), [ML forecast metadata](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/forecasters/ml.py#L104).

LangGraph's new batch contains four successful forecasts and four successful `plan → retrieve → research → critique` traces:

| Topic | Sampled question | P(YES) |
|---|---|---:|
| Electricity | `power-mean_gt-DE_LU-2026-11-17-v2` | 33% |
| Weather | `weather-gust_gt-hamburg-2026-11-17-v2` | 62% |
| Wikipedia | `attention-views_ge-enwiki.Godzilla_Minus_Zero-2026-11-17-v2` | 63% |
| Currencies | `markets-absmove_gt-EUR_JPY-2026-11-17-v2` | 50% |

Evidence: [forecasts](https://github.com/JASHD12/forecast-arena/blob/958194904fce6c50b5f0b5a1513af3853dcb645e/forecasts/2026/11/16.jsonl), [agent traces](https://github.com/JASHD12/forecast-arena/blob/958194904fce6c50b5f0b5a1513af3853dcb645e/agent_traces/2026/11/16.jsonl), [one-per-domain default](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/agent/graph.py#L73). On 14 November there was one genuine LangGraph HTTP 400 tool-result error; 15 November produced three successful forecasts and 26 sampling skips. Preserve the old error and distinguish it from current behavior.

The [leaderboard](https://jashd12.github.io/forecast-arena/leaderboard.html) is built from scored forecasts. At the inspected snapshot, all 33 ML forecasts are unresolved. Its scored heatmap, race and calibration consequently cannot report an ML score. There is a second distinction: `agent_graph` is deliberately outside the registered headline comparison groups. Its scored samples can appear in exploratory heatmaps/head-to-head comparisons. The all-questions board requires coverage of the entire selected reference population; historical missing ML forecasts can keep ML ineligible for the full rehearsal scope even after new ML forecasts resolve. **Do not quietly shrink that scope or change preregistered groups.** Add explicit participation and eligibility displays plus clearly separate paired diagnostics. [Groups and coverage rules](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/scoring/boards.py#L20).

### B2. Technical inventory

Status abbreviations: **L** live evidence; **C** current CI evidence; **T** locally executed tests/reproduction; **S** source/artifact inspection only; **P** partial integration; **D** intentionally disabled; **F** reproduced defect; **W** future or owner acceptance. These states can coexist. High confidence means direct execution or immutable records support the stated behavior; it does not mean every input is covered.

| Feature / production entry point | Intended inputs → persisted outputs | Observed status and evidence | Confidence / remaining verification |
|---|---|---|---|
| SMARD electricity / `ops.wiring.build_domains`, `PowerDomain` | Timestamped hourly prices → as-of snapshots, six question types, resolutions | L/C/T; live questions and outcomes; DST/missing-hour/revision tests. R01 finds invalid-number path. | High for normal path; malformed numbers need repair. |
| DWD/Bright Sky weather | Forecast/observations for four cities → weather questions/context/outcomes | L/C/T for questions and inference; recorded fixtures and gateway tests. New live weather outcomes not yet present. | High inference; W live resolution across full domain lifecycle. |
| Wikimedia/Wikidata attention | Available article trajectories/metadata → questions/context/outcomes | L/C/T for questions/inference; fixtures, exclusion/as-of tests; newly enabled live outcomes pending. | High inference; W complete live resolution. Do not invent a verified pageview licence. |
| ECB currencies | Published reference fixings → returns/questions/outcomes | L/C/T; four Monday questions; weekend/holiday/missing-fixing tests. | High inference; W first live resolution in current rollout. |
| CoinGecko crypto | Demo key and approved terms → prices and optional domain | D/C/T fixtures; owner H12 unresolved. | Disabled intentionally; no daily requirement while disabled. |
| Base rate, persistence | Eligible past outcomes → one probability/question | L/C/T; all 74 questions have baseline forecasts. | High; preserve eligibility and as-of tests. |
| Electricity HGB quantile model | Last 28 known days + calendar → calibrated probability | L/C/T; six new forecasts, promoted artifact, real fresh-process E2E. | High current inference; W first live scores. |
| Electricity LightGBM/Optuna and PyTorch quantile models | Time-ordered training → challenger evaluation/artifacts | C/T plus live weekly challenger evidence; both can reload in minimal inference environment. | Challengers, not additional daily forecasters. No requirement to show every family as a live row. |
| Attention HGB / LightGBM | Available trajectories → calibrated classifier probability | LightGBM champion L; HGB challenger; fixture/unit and weekly evidence. | High current inference. Stale HGB-only site wording needs R05. |
| Weather rules / markets EWMA Student-t | Numerical forecast or past returns → domain probability | L/C/T; 15 weather and four currency ML forecasts. | Analytical/rule models, not newly trained neural models. |
| Crypto EWMA model | Past crypto prices → probability | D/C/T; fixtures only in current operation. | Keep disabled pending source authorization. |
| ETS, SARIMAX, Chronos-Bolt | Known historical series → benchmark predictions/cards | Backtest-only, committed cards; unit paths use available dependencies/fakes as appropriate. | S/C/T vary by benchmark; full year backtests and Chronos weights were not rerun/downloaded in this audit. |
| Weekly retrain/evaluate/refit/promote / `ops.weekly` | Fixed comparison window and candidate recipes → decision summaries, artifacts, promotions | L/C/T; 15 Nov live publication; invalid-candidate/final-refit regressions. | High publication; R06 display mismatch. Future live replacement W. |
| Registry / `forecasters.registry`, `ops.wiring.live_ml` | Hash-checked eligible promotions → loaded models/errors | C/T and real current L inference; three minimal-runtime artifact families reload in fresh interpreter. | High; keep per-domain failure isolation. |
| Plain/context LLMs / `forecasters.llm` | Question or available context → strict JSON probability + brief public summary | L/C/T; repaired structured parsing, refusal/retry tests; live versions recorded. | High mechanics; quality evaluated separately, small frozen set. |
| Plain agent / `agent.forecaster`, tools | Context + bounded read-only tools → forecast/skip, tool traces | L/C/T; live success; historical errors retained. Tools need not be called on every answer. | High mechanics; R16 strengthens factual-grounding evaluation. |
| LangGraph / `agent.graph` | Sampled question → graph stages, summary, forecast and trace | L/C/T; four new successes, 29 sampling skips. | Working sampled service; R03/R04 explain omissions. |
| RAG / `agent.retrieval` | Earlier resolved questions + embeddings → eligible similar examples | C/T, configured in live graph/agent version and traces. | Leakage filter tested; real semantic retrieval quality is not proved by adapter wiring. |
| Local Qwen / llama.cpp | Same context contract → local probability/summary/trace | L; pinned weight revision restored by morning; mocked unit tests. | No new download during audit; text can contain unsupported factual claims. |
| LLM budgets/tracing/OTLP | Per-attempt known/reserved usage → manifests, spans, exported JSON | L/C/T; refusal/cache/retry/restart tests; Nov 16 reported 149,989/150,000 budgeted tokens. | Close to cap; monitor, do not raise cap merely for more rows. |
| Frozen LLM eval / `evals.run` | 12 fixed power questions → versions, validity, quality/cost metrics | Existing real artifacts + C/T fake provider; no paid calls in audit. | R15 pins comparison; no broad accuracy claim from n=12. |
| Canonical scoring/findings | Eligible forecasts and first valid outcomes → Brier/log, paired intervals, hypotheses | C/T; ordinary/void/source-revised, incomplete roster, inconclusive tests. | Preserve official/rehearsal/backtest distinctions. |
| DuckDB/Parquet/dbt/notebook/Polars | Canonical eligible records → exports, SQL views/marts and analysis | C/T; current CI executes notebook/dbt, same-fixture consistency tests. | R02 query mutation; exploratory versus headline scopes intentionally differ. |
| Static JSON API | Same site records → questions/latest/leaderboard and schemas | L/C/T; downloaded JSON; no skip/trace/explanation participation schema currently. | R03/R04 additive extension; do not call current narrow contract a broken endpoint. |
| REST/FastAPI and MCP | Local ledger snapshot → queries over memory/record views | C/T; HTTP TestClient + MCP transport tests; Docker/kind CI. | R02 confirmed mutation; no publicly hosted REST/MCP endpoint claimed. |
| Streamlit dashboard | Parquet export → interactive local dashboard | C AppTest; public hosting absent, owner H19 optional. | W hosting, not a core-site outage. |
| Human panel / player intake | Approved pseudonymous CSV before lock → forecast records | C/T validation; real intake W H06/H15. | No invented users/feedback; ensemble is a planned later capability, not a missing registered daily implementation. |
| Ledger / scheduled jobs | Atomic appends + before-lock commit → seals, manifests, health, execution/audit evidence | L/C/T; local verification at9581949 passes **105 files, four batch seals, three day seals, 290 forecasts**. | R01 finite schema gap; no live corruption found. |
| Official start | Five completed clean UTC days + owner not-before → immutable start file | C/T; missing evidence fails closed; no start file. | W five clean days and owner date. Does not activate ML. |
| CLI subcommands | Help advertises generation/forecast/resolution | Three low-level commands reproduce exit2 stubs; production `daily` commands work. | F, R10. |

### B3. Website route and state coverage

The read-only crawl fetched **132 same-site resource URLs**, including **115 HTML URLs / 114 distinct HTML paths** (root and `index.html` duplicate), with no failed internal destinations or anchors. It checked 74 individual question pages, four filtered archives, eight forecaster profiles, four topic profiles and their indexes, and 21 top-level HTML pages. Rendered browser review covered every distinct top-level page and every topic/profile/archive template, with mobile profiles and four representative question states/domains; generated question collections were comprehensively link-checked and sampled visually. It was not a hand inspection of every pixel of all 74 question pages.

| Pages / template | Verification and observed state | Needed change |
|---|---|---|
| Home | Desktop1366×768/mobile 390×844; real counts, model rows, charts and empty common-set state | R03 status states; R12 shorter candidate/proof hierarchy; R11 avoid calling every ML domain gradient boosting. |
| Recruiters | Both sizes; abstract intro + activity KPIs; name/role/contact and strong result absent from first screen | R12; owner profile facts pending. |
| About, German | Rendered; name exists on About; German generic project summary and proofreading note | R12 approved professional contact; R14 localized hiring entry, owner proofreading H17. |
| Leaderboard | Rendered; true zero-scored ML state, fixed common-set empty; sort works | R03 participation/eligibility, explicitly scoped sampled comparisons. |
| Questions + four topic filters | All routes fetched; search0/74→74/74 and Weather30/30 reset verified | R03 consistent state labels and sample destinations. |
| 74 question pages | All routes fetched; power resolved/open, attention trace, weather/currency latest sampled | R04 ML explanation and universal participation, not fabricated trace text. |
| Eight forecaster profiles/index | Rendered; ML33/0scored, graph7total/1scored; graph topics derived only from scored records | R05 separate forecast topics from scored topics. |
| Four topics/index | Rendered; correct no-outcomes states, source links and question types | R03 eligibility/help; preserve source attribution. |
| Calibration / race charts | Rendered; intentionally no ML calibration at0scored | R03 awaiting-data card + actual required sample, keep thresholds. |
| Backtests | Six model cards, clearly labeled; losing models shown | Retain; R12 link strongest proof directly. No rerun of every full backtest. |
| Experiments | Live decision summaries + contradictory candidate “not promoted” | R06; R17 separates prospective diagnostics from refit-window diagnostics. |
| Evals / LLM observability | Rendered; separate small evals, live costs/errors and OTLP export | R15 comparable evidence; R03 clear sampling in reliability denominator. |
| Stack / Methods / Guide | Rendered; stale ML status, no-JS claim and schedule text | R05/R11. |
| Data / API | Resources fetched, tables/dictionaries render; inline long paths/code overflow on mobile | R02/R03/R13; static contracts differ from interactive SQL. |
| Status | Latest successful manifests, historical clean-day failures, skip counts | R07 final-workflow/health/deploy states; R03 per-model reason totals. |
| Play | Live and practice rounds reveal correct Brier arithmetic; slider/search/theme/sort work | Preserve; no real human submission was sent. |
| Imprint / Privacy /404 /feed | Routes fetched and rendered where HTML; existing legal owner tasks remain | Owner H14; no new legal-compliance claim. Privacy has overlapping generic/owner sections; consolidate cautiously. |

Current CI runs axe checks on all non-question pages plus five question samples at1200 light/390 dark, and tests no-JS home/archive/play fallbacks. The audit additionally checked live mobile/desktop rendering, game, search, filter, sort and theme. Full manual keyboard traversal, print rendering, all no-JS routes, all theme×viewport combinations and real-reader comprehension remain acceptance work. Do not report automated accessibility coverage as complete usability proof.

Performance: inspected static resources are small (app.js10,563 bytes; CSS40,183; latest home98,092 uncompressed bytes); the frontend has no framework bundle, external font or required third-party request. Sample HTTP timings were roughly170–280ms in this audit environment, with Pages cache headers; these are **not LCP/INP/CLS measurements**. No DevTools trace/Lighthouse/field-vitals tool was available. Retain the small functional JS; no measured case justifies a framework migration or asset-removal project. Add bounded lab measurements to rollout, without inventing scores.

### B4. Checks actually executed or inspected

| Check | Outcome |
|---|---|
| Local lint/format/mypy | Pass; format256 files, mypy119 source files. |
| Local unit suite with coverage | 597 passed +three setup errors caused by sandbox localhost binding. Those three tests rerun with permitted local binding:3 passed. Combined verification covers600unit tests; the initial `make check` invocation itself did not exit successfully. |
| Separate offline E2E | 7 passed; includes real HGB/LightGBM/PyTorch weekly→artifact→fresh interpreter→production morning paths. |
| Current source CI43740896689 | Eight jobs successful. Unit job 597 passed,3 skipped; E2E7 passed;89% rounded coverage. Dedicated inference job all three families pass. |
| README generation | `scripts/readme_sections.py --check` passes. Generated content can still be unhelpful or weakly scoped. |
| Badge check | Current CI checks it. Local audit's standalone `--check` omitted its required XML arguments and printed usage; it is not counted as a local pass. |
| Live-snapshot ledger verify --git | Pass at9581949:105 files,4batchseals,3dayseals,290 forecasts. |
| Public-route/anchor crawl |132 resources,115HTMLURLs/114uniqueHTMLpaths; no internal-link/anchor errors. |
| SQL boundary reproduction | CTE-prefixed DELETE accepted in MCP and REST; forecast count1→0 in memory; ledger file stillhas1 row. |
| Invalid-number reproduction | Parser acceptsNaN/Inf/bool; a NaN target-hour fixture resolves outcome0, storesNaN, verify reportsOK. |

No new paid provider calls, model-weight downloads, live training, external source backfills or production workflow triggers were used. Existing real records and CI logs supplement fixture-based execution.

## C. Findings and required resolutions

Operational priorities: P1 can compromise correctness, observability or a deadline; P2 functional/product inconsistency; P3 optional improvement. Hiring priorities H1/H2 are separate and do not override integrity work. Estimates are engineering effort ranges for an informed agent, excluding owner response and future-run waiting.

### R01 — Reject nonfinite source observations and ledger values

**P1 correctness; high confidence; reproduced locally; 0.5–1 day.** `sources/smard.py:85–97` accepts `float('nan')`, infinity and bool-as-number. Replacing one target-day hourly value with NaN in the recorded power fixture makes `PowerDomain.resolve` emit outcome0 and observedNaN; `Resolution.observed_value` has no finite guard, canonical JSON permitsNaN, and unsealed-ledger verification returnsOK. This is a demonstrated malformed-input path, **not evidence of malformed live outcomes**. [Parser](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/sources/smard.py#L85), [resolver](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/domains/power.py#L404), [schema/serializer](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/models.py#L146).

Repair numeric boundaries in source parsers and typed records, and serialize canonical JSON with nonfinite values rejected. Inspect other parsers with float conversion under the same policy. Invalid numeric data must remain unavailable/diagnosed and follow existing retry/grace/void behavior, never become a confident NO or a guessed0. Validate nested evidence/snapshot numeric payloads where part of the contract. Do not change legitimate null semantics or historical bytes.

Regression: recorded ordinary power question +oneNaNhour; ±Inf and booleans at input; nonfinite threshold/observed/evidence serialization; valid zeros/negative electricity prices; existing23/25 hour tests. **Done:** invalid inputs cannot produce a scored resolution or nonstandard canonical JSON, errors are explicit, normal/missing-data lifecycle and ledger seals still pass. Audit any existing nonfinite historical bytes read-only; if found, propose append-only corrections under existing rules.

### R02 — Enforce the SQL interface's read-only contract

**P1 local service consistency; high confidence; 0.5–1 day.** `WITH allowed AS (SELECT 1) DELETE FROM forecasts RETURNING forecaster_id` passes `check_sql` and mutates the shared in-memory DuckDB snapshot. REST returnsHTTP200; MCP returns deleted rows; subsequent SQLcount falls1→0 while the file and Record view remain intact. External-access restrictions do not prevent DML. [Validator](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/mcp_server.py#L36), [execution](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/mcp_server.py#L145).

Use actual statement parsing/type validation and/or a properly read-only execution context, preferably with the existing engine before adding a SQL dependency. Require exactly one permitted SELECT query, including legitimate CTE SELECTs; reject mutation, configuration and multi-statement paths. Keep file/network access disabled. Validate the exact DuckDB API in the pinned version during implementation.

Regression: CTE DELETE/UPDATE/INSERT, comments, whitespace, multiple statements, benign semicolons in string literals, legitimate nested CTE SELECT, external-table functions. Test MCP and REST and assert row counts/views remain unchanged after refusal. **Done:** both interfaces reject mutations, preserve valid reads and limits, and cannot change shared query state.

### R03 — Show participation, sampling and scoring eligibility everywhere

**P2 usability, H1 hiring; high confidence; 1–2 days.** The user-visible missing-ML complaint is reproducible even though inference works. Scored-only collections remove zero-scored forecasters; homepage gaps say only“–”; graph skips are terse; old missing ML has no skip because the old factory never registered it. This obscures distinct states. [Build inputs](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/site/build.py#L204), [homepage bars](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/site/templates/index.html#L4), [board coverage](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/scoring/boards.py#L95).

Build a shared display view of expected/configured participation, forecasts, skips, unresolved/scored counts and scope eligibility. Show all applicable forecasters in a **participation section** even with no score. ML example:“33 forecasts published ·0resolved ·awaiting outcomes”. Graph example:“4/4selected questions answered ·29outside daily sample ·0 errors”. Historical unrecorded pairs must say“no record in this historical batch”, not be turned into new skip records. Distinguish pre-morning/not-yet-due, disabled, notsampled, budgetexhausted, modelmissing, error, unanswered and awaitingresolution.

Keep existing headline groups and full-scope eligibility. Excluded rows need a reason and denominator. Add a separate explicitly exploratory paired table for each active forecaster versus base rate on the same resolved questions; include sample N/days, scope and uncertainty rules. Keep graph outside the preregistered headline unless the owner separately approves a prospective design decision. No zero scores, manufactured confidence intervals or ordering of unscored entries. A small-sample state must not imply superiority.

Components: `site/build.py`, a shared shaping/view module, `scoring/boards.py` only for additive eligibility metadata, home/leaderboard/topic/profile/calibration/status templates, `site/api.py` and schemas where exposed. Preserve v1 compatibility with optional additive fields or introduce a documented version if necessary. **Done:** a user can answer“did this model run, why is there no number, and when can it be scored?” from each relevant page. Fixtures cover newML0scored, partial historicalML, graphsampling, realerror, disabled and empty/pre-morning states; HTML/API counts agree.

### R04 — Add model-method evidence without fabricated reasoning

**P2 product, H1 hiring; high confidence; 1–2 days basic display, 2–4 days additional prospective inference diagnostics.** Replace the LLM-only implication with clearly named sections: **Published AI summaries** for existing short provider text, and **Forecast method and run evidence** for all forecasters. Retain existing traces; do not request or expose hidden model thinking. The skipped graph row should explain sampling and link to its sampled question/trace for the same topic/day. A sampled graph answer must show its recorded graph path, tools, versions and call counts.

For existing ML forecasts, render only available evidence: domain, algorithm/version, model/artifact hash, source/context snapshot when reconstructable from existing records, forecast timestamp, question threshold/rule, model-card link and recorded promotion/training metadata. State plainly that no per-question attribution was recorded. Do not generate an LLM rationale and present it as the original model's explanation. Global feature importance is not a local explanation; an absent SHAP panel for an HGB winner is not proof inference failed.

For future forecasts, design a small versioned optional explanation artifact recorded **before lock**: input snapshot identity/as-of cutoff, feature schema, relevant statistic, quantiles/raw probability/calibration output where the model supports them, and method-specific diagnostics. Weather rules, currency Student-t and attention classifier need their own truthful descriptions. Ensure displayed final probability agrees exactly with the stored forecast and retain provenance. Prefer deterministic templates and a small CDF/threshold chart for power. Diagnostics failure must not silently alter a valid forecast; record its availability explicitly.

Files: `forecasters/ml.py`, family-specific models only for optional diagnostics, typed explanation contract, `ops/jobs.py` persistence if needed, `site/build.py`, `site/templates/question.html`, API export/schema and focused tests. Preserve historical ledger bytes; label any later reconstruction as post-hoc and keep it outside original forecast evidence. **Done:** target question shows ML19% with its real method/provenance and graphsampling explanation; a graphsample page shows its actual summary/trace; no invented explanation or fake tool call appears. Tests cover answered/skipped/oldmetadata/missingartifact/diagnosticfailure per family.

### R05 — Correct live model inventories, domains and profile labels

**P2 content correctness, H1; high confidence; 0.5–1 day.** `live_versions` groups only by forecaster ID and shows one latest ML version, hiding the other domain models. Profile topics derive only from scored rows, so graph says onlyElectricity despite four-topic inference. `INFORMATION_SETS` still saysplanned; Stack says MLjoinslater and describes HGB attention although the champion isLightGBM. [Version shaping](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/site/shaping.py#L48), [profile topics](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/site/profiles.py#L59), [stack](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/site/templates/stack.html#L12).

Group production versions by domain+forecaster; show `power-gbq-r1-2026-11-12`, `attention-lgbc-r1-2026-11-07`, `weather-rules-r2`, `markets-ewma-t5-r1`, with last publication and roles. Separate trained/promoted/currentlyforecasting/scored states. Show forecasted topics and scored topics separately, and derive cadence from configured policy rather than a genericplanned string. Keep model-family identity distinct from forecaster identity. **Done:** all four models appear, graph's four topics appear with correct score availability, stale future-tense claims disappear, and a fixture with a future promotion does not retroactively rename old versions. Coordinate shared view ownership withR03.

### R06 — Fix false “not promoted” labels

**P2 correctness; high confidence; 2–4 hours.** Candidate versions were evaluated with an earlier cutoff; the selected recipe was refitted and published with a later version. `experiments.html:26` compares those version strings and labels both actual winning families“not promoted”. [Template](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/site/templates/experiments.html#L26).

Render the selected evaluated family and the separately identified refitted promotion artifact; a selected candidate is not necessarily a successfully published artifact when refit fails. Use explicit decision state plus `best_family`/promotion outcome, retaining legacy summary handling. **Done:** the15Nov attentionLightGBM and powerHGB winners read“selected; refitted artifact promoted <version>”, other families retain actual reasons; failed evaluation/refit/no-improvement cases do not showpromotion. Render tests use real summary shape and synthetic failure summaries. No model/ledger change is needed.

### R07 — Reconcile incident state with final workflow outcomes

**P1 monitoring; high confidence source path and real deployment failure; 1–2 days.** Incident update occurs before the final health exit and separate deployment job. Setup failures can happen before it; a successful application can close an incident before Pages/smoke fails. Existing durable completed-day audit correctly blocks clean-day readiness but is not a complete immediate alerting mechanism. [Morning incident stage](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/.github/workflows/morning.yml#L165), [observer](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/.github/workflows/workflow-evidence.yml#L18).

Add trusted completed-run reconciliation covering setup, application, health, ledger publication, deploy and smoke. Identify run/attempt, keep per-subsystem unresolved failure state, make incident updates idempotent, and require qualified recovery from the relevant subsystem. Dry/noop/disabled jobs cannot clear an unrelated deployment failure. Preserve completed-day readiness rules and immutable failures. Status must distinguish latest application manifest from final workflow outcome. Tests mock API forsetupfailure, passingapp+deployfailure, smokefailure, retry, unrelatedsuccess, oldrerun and optionaldisabledjobs. **Done:** final failures are visible without an application manifest; unrelatedgreen runs cannot hide them; incident text reports stage statuses accurately. No issue mutations during planning; implementation uses existing incident authorization only.

### R08 — Triage vulnerable packaging pins and audit actual environments

**P1 dependency hygiene; high confidence; 0.5–1 day.** Current green [CI audit job 132893600957](https://github.com/JASHD12/forecast-arena/actions/runs/43740896689/job/132893600957) reports five advisory rows for `setuptools78.1.0`, representing three unique advisories. Pins occur in `requirements/torch.txt:10` and `requirements/ts.txt:45`; torch is included by inference. The audit is deliberately advisory, so green does not mean no advisories. [PyPA advisory1](https://github.com/pypa/setuptools/security/advisories/GHSA-5rjg-fvgr-3xxf), [advisory2](https://github.com/pypa/setuptools/security/advisories/GHSA-h35f-9h28-mq5c), [advisory3](https://github.com/pypa/setuptools/security/advisories/GHSA-xmj3-9gf7-h52w). Exploitability depends on packaging/platform paths; no compromise was demonstrated.

Select a compatible maintained version after checking current releases/advisories; regenerate coherent affected locks in isolated environments. Audit base, inference/local, training/time-series, dbt and constrainedAirflow separately; do not merge incompatible locks. Save machine-readable results and unique IDs; distinguish findings from auditorfailure; document narrow expiry-based exceptions if unavoidable. Decide gating policy separately rather than silently suppressing rows. **Done:** fresh installs+`pip check`, no untriaged advisories, existing CI and minimal-runtime artifact tests pass. Coordinate dependency ownership withR04/runtime tests.

### R09 — Complete the existing scheduler/dispatch follow-up

**P1 deadline reliability; confirmed late starts, specific queue cause partly unverified; 0.5–1 day preparation +owner/future run.** New morning started at06:27 UTC versus first00:15slot and finished pre-lock. Prior days also started hours after the first slot; this does not prove which exact cron invocation was delayed versus dropped. Shared ledger concurrency can delay critical work. Owner taskH20 already describes an external trigger. [Run](https://github.com/JASHD12/forecast-arena/actions/runs/43816839671), [existing task](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/docs/project/HUMAN_TODO.md).

Prepare a concrete owner-operated bounded external trigger with minimal Actions credentials stored by the owner, actual deadline alerts and checked-code policy. Schedules runstable; dispatch fromstable currently violates Pages environment policy. Enforce live dispatchmain→explicitstablecheckout, or require main==CI-approvedstable immediately before dispatch; allow testref dry runs separately. Do not loosen deployment protection to improve appearance. Reproduce queue/deadline contention before choosing queue changes; a longweekly FIFO backlog can worsen morning latency. **Done:** a future real batch lands pre-lock without manual rescue; late runs refuse work; code/ledger provenance is correct. Account/service/token setup remains owner-only and is not performed by this plan.

### R10 — Remove or implement misleading CLI stubs safely

**P2 developer functionality; high confidence; 0.5 day.** `questions generate`, `forecast run`, `resolve run` are advertised but call `_not_yet('T027')` and exit2, whileT027 is complete and dailycommands work. [Commands](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/cli/jobs.py#L38).

Choose documented deprecation/removal with precise supported command guidance, or genuinely scoped implementations consistent withSPEC. Never alias a harmless-sounding generation command to a full paid/network morning job. **Done:** all advertised commands behave as documented, help and examples agree, fake-provider temporary-ledger CLI tests verify no unexpected calls/writes.

### R11 — Refresh operational and factual content from shared sources

**P2 trust; high confidence; 0.5 day.** SPEC prose, old timeline table, Runbook, homepage, Status, `_arch.html`, Stack and README disagree about schedules/current domains. Stack says“no JavaScript” while self-hosted app.js supplies working interactions. Progress/T057/T193e still wait for the now-published batch. Some copy implies five days alone starts official scoring, omitting ownernot-before. Recruiter/DE fixed“$1/month” is a budget estimate rather than computed current invoice.

Use one schedule/status source where practical, update templates and generated-content producers, and clearly scope budget estimates versus measured usage. Preserve historical validation text with a dated update rather than changing the old snapshot's meaning. T057/T193e can be reconciled against actual new inference evidence; separately leave resolution/future promotion checks pending. **Done:** schedule/source/config-aware tests plus generated README checks agree, no static future-tense claims contradict current records, no unsupported fixed cost or no-JS claim remains. Do not change official gates or owner date.

### R12 — Make the hiring landing page explain the candidate and strongest proof

**H1 presentation; high confidence; 1–2 days after approved profile details.** Recruiter first screen has a generic project title and activity counts; homepage has a long abstract, four actions and an empty standings area ahead of strong backtest evidence. Neither identifies candidate/targetrole immediately. Existing owner details are suppressed by the unfinished-content guard. GitHub README opens around1485px below native repository controls/filelist at 1366×768; README alone cannot solve the repository first screen.

Use `recruiters.html` as the primary application link. Provide a concise candidate hero, one real proof card, two actions and three role-specific evidence paths. Keep broader benchmark navigation. Add an approved contribution narrative distinguishing direction/specification, personal engineering/analysis and agent implementation; project features do not establish candidate mastery. Prepare copy in sectionE, render desktop/mobile and print, keep unknown facts unpublished. **Done:** role/name/purpose/proof/action visible at 1366×768 and390×844, with 390×700 checked; measured artifact link appears next to the result; no invented CV, enrolment, language or ownership claim. Human test sectionH remains separate.

### R13 — Expose mobile hiring navigation and contain long text

**P2 usability, H1; high confidence; 0.5–1 day.** At390px, `For recruiters` sits approximatelyx538–648 in a horizontally scrolling primarynav, hidden beyond the visible strip; it is not duplicated underMore. The theme button also consumes a separate row. Data's long dbt source paths cause bodywidth471px; Guide's inline clone commands cause403px. [CSS](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/site/static/style.css#L610), [Data source links](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/site/templates/data.html#L25).

Give mobile a clear visible recruiterlink or complete accessible menu without reliance on undisclosed horizontal swiping; keep keyboard/native details/no-JS operation. Wrap long inline paths and use contained scrollblocks for commands; preserve intentional table scrolling. The leaderboard's wide tables already have scroll wrappers, so do not label table width alone a page-layout failure. **Done:** primaryactions accessible, page body does not overflow at320/390/768/1366 except intentional local regions; keyboardfocus visible; no-JS menu usable; axe checks and meaningful rendered interaction checks pass.

### R14 — Fill GitHub metadata and make share previews specific

**H1; high confidence; 0.5 day assets/copy +owner settings.** GitHub's current description/homepage are null and topics empty; rendered About says noneprovided. Shared description and1200×630 preview are generic project content on every route. [Repository](https://github.com/JASHD12/forecast-arena), [base metadata](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/site/templates/base.html#L9).

Prepare description, recruiter URL, accurate topics, ownerpinning instructions and a repository preview asset; owner applies settings. Website recruiter/DE metadata should identify target audience and approved candidate details; benchmark pages retain their own titles/descriptions. Use concise self-hosted proof-based artwork, useful alttext and appropriate canonical/language tags. Different platforms may need different dimensions; follow current official upload guidance during implementation. **Done:** copy/assets ready for review, owner-applied settings separately verified, sharedlink preview is legible and truthful; no nonexistent contact/CV destinations.

### R15 — Pin and scope the LLM engineering result

**P2 evidence reliability, H1; high confidence source/artifacts; 0.5 day.** README and recruiter generators choose oldest/newest non-schema evaluation automatically. That can later compare different datasets/models/settings. Current claimed validity change is2/12→12/12 first-try JSON; this is format compliance, not improved forecasting accuracy. The later plain-model Brier is0.2634 versus earlier0.2375; caching/settings also differ, so do not claim a single controlled causal intervention. [README producer](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/scripts/readme_sections.py#L81), [site producer](https://github.com/JASHD12/forecast-arena/blob/b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa/src/arena/site/shaping.py#L257).

Create an explicit comparison definition identifying artifacts, goldenhash, variant, metric, denominators and changed settings; share it across website/README/CV producers. Label smallsample and observational before/after limits. **Done:** adding an unrelated future eval cannot rewrite the headline; mismatched dataset/model fails comparison validation;2/12 and12/12 are reproducibly generated; no validity-to-accuracy conflation. No paid rerun is required for this display correction.

### R16 — Strengthen factual-grounding evaluation of public LLM summaries

**P2 capability/evidence improvement; observed model behavior, not proof of source leakage; 1–2 days offline harness/data work.** On the reported unresolved question, the local model asserts a17Nov evening price as though known and saysNO while emitting55%YES. The site correctly labels summaries as machine-generated, but JSONvalidity alone does not catch unsupported facts or probability/text inconsistency. Preserve that published summary; do not tune a prompt to this live outcome.

Add a future frozen evaluation set and rubrics for grounded numeric references, date/as-of discipline, abstaining from unsupported observations, and consistency between short summary and probability. Use available frozen fixtures and scripted bad/good outputs for harness tests; if an automated judge is proposed, measure it against owner-reviewed labels and separate paid evaluation. Publish representative failures and sample sizes; improvements require versioned prompts and appropriate offline comparison. **Done:** format and grounding metrics are distinct, falsefuture-observation examples are caught by tested checks/rubric, provider claims are never shown as resolutionevidence, and no historical text is rewritten.

### R17 — Separate refit-window diagnostics from prospective evaluation

**P2 methodological improvement; source-confirmed scope, no allegation of concealed overlap; 1–3 days.** Weekly diagnostics are computed using the promoted/refitted power model on a window that can overlap its training. The conformal section already warns coverage may look optimistic. Keep this warning and extend explicit model cutoff/dataset role labels to importance, pinball and coverage panels. Distinguish development diagnostics from held-out performance.

If stronger portfolio evidence is worth the effort, calculate diagnostics with the pre-window evaluated model or truly later untouched data, using separate fit/calibration/evaluation splits appropriate to time series; do not promise distribution-free time-series guarantees without assumptions. **Done:** every panel identifies evaluatedartifact, fitcutoff, evaluation dates and overlap flag; a future held-out report cannot train/calibrate on its evaluation targets. Existing weekly selection rule remains unchanged unless separately approved.


## D. German working-student job evidence

Verified on **2026-11-16**: **24 unique postings across 23 employers**; eight per category. Full official employer/authorized ATS descriptions were opened. Accessible pages/application links are evidence of accessibility, not a guarantee vacancies are unfilled.

Purposeful convenience sample, not a representative market estimate. Dates are displayed publication dates only where available; all other dates below are verification dates. No exact publication date is inferred from crawler recency.

Task-content classification with overlap. Bundesdruckerei titled Data Science is classified AI/LLM because the sampled duties explicitly cover LLM/RAG evaluation and AI platform. Highberg Data & AI Engineering is classified ML/MLOps. DS includes adjacent data analytics roles (1KOMMA5 and Mobility Data Space) and data technology (Cogitaris). These are not eight pure DS titles.

### Frequency counts

Each skill is counted at most once per posting. Cells are `any mention / denominator (R,A,I,P,W,D,S)`. R=explicit requirement; A=accepted alternative; I=interest/familiarity; P=preferred; W=may learn; D=duties; S=stack only. The coding matrix below makes every count auditable.

Evaluation coding counts model/application quality testing, validation, benchmarks or performance evaluation. AI-assisted coding output review and generic statistical experiment design are recorded in source records but excluded from model-evaluation counts.

#### AI/LLM (n=8)

|Skill|Any mention|R|A|I|P|W|D|S|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|Python|6/8|4|1|0|1|0|0|0|
|SQL|1/8|1|0|0|0|0|0|0|
|ML|3/8|2|0|0|0|0|1|0|
|statistics|0/8|0|0|0|0|0|0|0|
|LLM|8/8|4|1|3|0|0|0|0|
|evaluation|7/8|0|0|0|0|0|7|0|
|Git|4/8|2|0|0|1|1|0|0|
|Docker|3/8|0|0|0|2|1|0|0|
|cloud|3/8|0|0|0|2|0|1|0|

#### ML/MLOps (n=8)

|Skill|Any mention|R|A|I|P|W|D|S|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|Python|8/8|5|1|2|0|0|0|0|
|SQL|2/8|0|0|1|1|0|0|0|
|ML|8/8|3|2|1|2|0|0|0|
|statistics|1/8|0|0|1|0|0|0|0|
|LLM|3/8|1|0|0|2|0|0|0|
|evaluation|4/8|0|0|0|0|0|4|0|
|Git|3/8|1|0|1|0|0|0|1|
|Docker|5/8|2|0|0|2|0|0|1|
|cloud|3/8|0|0|0|2|0|0|1|

#### Data Science (n=8)

|Skill|Any mention|R|A|I|P|W|D|S|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|Python|8/8|6|2|0|0|0|0|0|
|SQL|5/8|3|1|0|1|0|0|0|
|ML|6/8|1|0|0|3|0|2|0|
|statistics|5/8|2|0|1|1|0|1|0|
|LLM|1/8|0|0|0|0|0|1|0|
|evaluation|2/8|0|0|0|0|0|2|0|
|Git|6/8|3|0|0|2|0|1|0|
|Docker|1/8|0|0|0|1|0|0|0|
|cloud|3/8|1|0|1|1|0|0|0|

### Coded matrix

|ID / employer|Category|Python|SQL|ML|Stats|LLM|Model eval|Git|Docker|Cloud|
|---|---|---|---|---|---|---|---|---|---|---|
|AI01 Bruski Smeets & Lange Rechtsanwälte|AI/LLM|R|-|-|-|R|D|-|P|P|
|ML01 inovex|ML/MLOps|I|I|A|-|-|-|I|P|S|
|DS01 ARAG SE|Data Science|R|R|R|-|-|D|D|-|R|
|AI02 Cargoboard|AI/LLM|R|-|-|-|R|D|R|-|-|
|AI03 smartvillage|AI/LLM|R|R|-|-|R|D|R|-|-|
|ML02 qbees|ML/MLOps|A|-|P|-|P|D|R|R|-|
|AI04 Brayn.io|AI/LLM|-|-|R|-|I|D|W|W|-|
|ML03 Highberg DACH (formerly SCHICKLER)|ML/MLOps|R|P|P|-|P|-|S|S|P|
|AI05 PROMOS consult|AI/LLM|-|-|-|-|I|-|P|-|-|
|ML04 DEUTZ AG|ML/MLOps|R|-|R|-|R|D|-|P|P|
|AI06 Bundesdruckerei GmbH|AI/LLM|R|-|D|-|R|D|-|P|-|
|AI07 SAP|AI/LLM|P|-|R|-|A|D|-|-|D|
|ML05 SAP|ML/MLOps|R|-|A|-|-|D|-|-|-|
|ML06 menio|ML/MLOps|R|-|R|-|-|D|-|-|-|
|AI08 plusserver|AI/LLM|A|-|-|-|I|D|-|-|P|
|ML07 GPI Consulting|ML/MLOps|R|-|R|-|-|-|-|R|-|
|ML08 dida|ML/MLOps|I|-|I|I|-|-|-|-|-|
|DS02 QuoData GmbH|Data Science|R|P|-|I|-|-|R|P|-|
|DS03 RTE Akustik + Prüftechnik GmbH|Data Science|R|-|D|D|-|D|R|-|-|
|DS04 Cogitaris GmbH|Data Science|A|-|D|-|-|-|-|-|I|
|DS05 Vodafone|Data Science|R|-|P|R|D|-|-|-|-|
|DS06 Tegtmeier Internet Solutions GmbH|Data Science|R|R|-|R|-|-|R|-|-|
|DS07 1KOMMA5°|Data Science|R|R|P|-|-|-|P|-|-|
|DS08 DRM Datenraum Mobilität GmbH (Mobility Data Space)|Data Science|A|A|P|P|-|-|P|-|P|

### Verified postings

#### AI01: Bruski Smeets & Lange Rechtsanwälte — Werkstudent KI / LLM-Entwicklung (m/w/d) mit flexiblen Arbeitszeiten

[Official description](https://bruskismeetslangerechtsanwltepartnerschaftmbb.heyrecruit.de/?id=137818&location=15948&page=job) · Frankfurt am Main · checked 2026-11-16 · source date: Page says updated three weeks ago; no exact publication date

Status: Full official ATS description and application form accessible
Responsibilities: Build and operate legal AI environment; RAG and document ingestion including PDF/OCR/chunking/embeddings; LLM API and self-hosted model integration; Evaluation, monitoring, logging and documentation
Candidate requirements: Python; LLM project experience; RAG/embeddings/semantic search
Preferred: Vector databases; Docker; Kubernetes; Cloud/on-premise; CI/CD; LLM evaluation/RAGAS/LLM-as-judge; Cost/latency tracking
Enrollment: Master in CS/Data Science/AI/ML/business informatics/math or similar; good bachelor degree at German university. Language: Very good German, good English. Arrangement: 15–20 hours; flexible hours; hybrid unspecified.

#### ML01: inovex — Werkstudent:in im Bereich Data & AI

[Official description](https://www.inovex.de/de/karriere/stellenangebote/werkstudent-in-im-bereich-data-ai/) · Karlsruhe, Köln, München, Hamburg, Berlin, Stuttgart, Erlangen · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full employer description and apply link accessible
Responsibilities: Data engineering and AI team work; Data platforms, ETL pipelines and ML deployments; Security, scalability and maintainability of data solutions
Candidate requirements: Initial Data Science or Data Engineering experience; Python familiarity; SQL familiarity; Clean code; Git familiarity; CI/CD familiarity
Preferred: Python; Pandas; PyTorch; Docker
Enrollment: Current master in relevant computing/math/industrial-engineering or similar field. Language: German C1 minimum; good English. Arrangement: Mobile work and flexible hours.
Coding note: Python/SQL/Git described as not unfamiliar; coded I (familiarity), not hard mastery. DS OR DE experience accepted. Cloud list is team stack, not candidate requirement.

#### DS01: ARAG SE — Werkstudent Data Science mit Python & Databricks (m/w/d)

[Official description](https://www.karriere-bei-arag.de/offer/werkstudent-data-science-mit-python/74845a4c-2be3-43b7-9ee7-e319954bed33) · Düsseldorf · checked 2026-11-16 · source date: No exact publication date; marked NEU and start immediately

Status: Full employer description and apply link accessible; job HR_DUS02091
Responsibilities: ETL/ELT pipelines in Databricks/Azure; Python analysis and visualization; Time-series/classification/clustering model implementation and validation; ML deployment, Git and CI/CD support; Finance stakeholder communication and documentation
Candidate requirements: Python; Pandas/PySpark/scikit-learn; Databricks; Azure; SQL; NoSQL; ML pipelines; Feature engineering; Model monitoring; DataOps
Preferred: None explicitly separated
Enrollment: Enrolled in quantitative degree e.g. Data Science/math/business informatics/statistics. Language: Native-level German and confident written/spoken English. Arrangement: Fixed-term part time; hybrid Düsseldorf.

#### AI02: Cargoboard — Werkstudent:in AI Engineering (all genders)

[Official description](https://cargoboard.jobs.personio.de/job/2876491?language=de) · Official ATS does not state city; description names Paderborn origin (Germany). Secondary listings identify Paderborn; not used for skills. · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer ATS description and application link accessible
Responsibilities: Maintain customer-support chat/email/phone bots; Adjust prompts and verify improvements; Build small automations and internal tools; document and explain decisions
Candidate requirements: Python; Git; LLMs; Prompting; Model APIs; RAG basics; Understand AI-generated code
Preferred: None explicitly separated
Enrollment: Studying CS, Data Science or similar. Language: Good German and English. Arrangement: Part time; homeoffice possible.
Coding note: Official full description and live application form opened; German GmbH employer. City missing from primary advert.

#### AI03: smartvillage — Werkstudent:in AI & Automation (m/w/d)

[Official description](https://smartvillage.jobs.personio.de/job/2804041?language=de) · München headquarter · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer ATS description and application link accessible
Responsibilities: Build LLM agents and finance automations; Prompt/context design, API integration and human escalation; Connect systems and improve quality through evals and monitoring
Candidate requirements: LLM APIs; Function calling/structured outputs/RAG concepts; Python; SQL basics; APIs; Git
Preferred: Finance; n8n/Make; HubSpot/CRM; Excel macros/Power Query
Enrollment: Current technology-related bachelor or master. Language: German C1 minimum and confident English. Arrangement: Part time, flexible hours; hybrid unspecified.

#### ML02: qbees — Werkstudent AiOps Engineer (w/m/d)

[Official description](https://qbees-gmbh.jobs.personio.de/job/1934991?language=de) · Ohlstadt / München · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer ATS description and application link accessible
Responsibilities: Build private/on-prem AI platform; Evaluate local LLM inference and write runbooks; AIOps anomalies, log analysis and RAG use cases; Integrate monitoring, GitLab automation and CI/CD
Candidate requirements: Linux; Networking; Python or Bash scripting; Docker/container deployment; Git
Preferred: Kubernetes; Local LLM inference; ML tooling; Ansible/Terraform; CI/CD; Observability; RAG/embeddings/vector search
Enrollment: Relevant CS/security/Data-AI/software engineering study. Language: Not specified. Arrangement: 10–20 hours typical; Ohlstadt and München workspaces; hybrid unspecified.

#### AI04: Brayn.io — Werkstudent:in Informatik / KI / Machine Learning (m/w/d)

[Official description](https://brayn.jobs.personio.de/job/1431815?language=de) · Berlin · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer ATS description and application link accessible
Responsibilities: Develop applications and tests; Integrate LLMs, evaluate models and extend foundation models; Automate business processes
Candidate requirements: ML/AI study focus; Software development project experience; Agentic frameworks; LLM/RAG/agent/knowledge graph/precision familiarity
Preferred: Git or willingness to learn; Docker or willingness to learn; Confluence/Jira or willingness to learn
Enrollment: Relevant enrolled student near bachelor completion or in master. Language: German C1 minimum. Arrangement: Preferably20 hours; hybrid with weekly Berlin Kreuzberg office meeting.
Coding note: ML/AI study focus and agentic framework experience required; LLM/RAG familiarity, Git/Docker familiarity OR willingness to learn accepted. Python is not named.

#### ML03: Highberg DACH (formerly SCHICKLER) — Werkstudent:in (m/w/d) im AI & Data Engineering

[Official description](https://schickler.jobs.personio.de/job/2860117) · Hamburg · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer ATS description and application link accessible
Responsibilities: Cloud data models, ETL and data warehouses; Analyze incomplete datasets and communicate results; Build ML/RAG/agent prototypes
Candidate requirements: Python; Data/AI engineering concepts
Preferred: SQL; Cloud; LLM applications; scikit-learn/PyTorch/Hugging Face
Enrollment: Enrolled with very good completed foundational study in quantitative field. Language: German C1 minimum. Arrangement: 15–20 hours, preferably>=6 months; Hamburg area resident, mostly office.

#### AI05: PROMOS consult — Werkstudent (m/w/d) - Software Development & AI

[Official description](https://promos-consult-gmbh.jobs.personio.de/job/2624543?language=de) · Berlin / mobile within Germany · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer ATS description and application link accessible
Responsibilities: Java application development; Integrate OpenAI/Claude APIs and build RAG systems; Research and prototype AI tools
Candidate requirements: Interest in Java; Interest in LLMs/prompt engineering/RAG
Preferred: Java experience; Git; REST/LLM API integration
Enrollment: Studying CS, business informatics or similar. Language: Not specified. Arrangement: Part time, flexible hours; office, homeoffice or mobile Germany.

#### ML04: DEUTZ AG — Werkstudent (m/w/d) Computer Vision & KI-Entwicklung (YOLO, LLM)

[Official description](https://career.deutz.com/job/K%C3%B6ln-Werkstudent-%28mwd%29-Computer-Vision-%26-KI-Entwicklung-%28YOLO%2C-LLM%29-NW-51149/1449721633/) · Köln HQ · checked 2026-11-16 · source date: 2026-10-21 displayed on employer page

Status: Full official employer/ATS description accessible; apply link accessible unless noted
Responsibilities: Train YOLO detection/classification models and develop LLM applications; Prepare training data; evaluate and tune models; Deploy container microservices and automated training/deployment pipelines; Implement monitoring and document architecture/results
Candidate requirements: Object-detection experience; LLM framework basics; Python; PyTorch/TensorFlow/OpenCV/Pandas; Interest in MLOps
Preferred: Azure; Docker; Kubernetes
Enrollment: Relevant CS/Data Science/AI/engineering or similar enrolled student. Language: Very good German and English. Arrangement: Maximum20 hours; fixed-term; hybrid unspecified.

#### AI06: Bundesdruckerei GmbH — Werkstudent - Data Science (m/w/d)

[Official description](https://jobs.bundesdruckerei.de/job/werkstudent-data-science-m-w-d/903-de_DE) · Berlin · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer/ATS description accessible; apply link accessible unless noted
Responsibilities: Data analysis, model training and evaluation; Develop/optimize RAG and other LLM applications with evaluation/monitoring; Build MLOps and internal AI-platform components; Coding standards
Candidate requirements: Data Science experience; Python basics; LLM experience
Preferred: Confident Python; Docker; Kubernetes
Enrollment: Current STEM/engineering or comparable study. Language: Fluent German C1minimum. Arrangement: 15or20 hours; fixed-term; hybrid unspecified.

#### AI07: SAP — Werkstudent (w/m/d) - Standard Software Entwicklung - SAP Transportation Management & KI

[Official description](https://jobs.sap.com/de/stellen/744000160556661/werkstudent-wmd-standard-software-entwicklung-sap-transportation-management-ki/) · St. Ingbert · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer/ATS description accessible; apply link accessible unless noted
Responsibilities: Develop and evaluate agents for multistep transport-management tasks; Functional/regression/AI-specific validation; Integrate AI solutions in S/4HANA private cloud
Candidate requirements: One object-oriented programming language; Practical AI/ML particularly NLP/LLM/GenAI experience
Preferred: Python
Enrollment: CS/business informatics/Data Science or similar study. Language: Very good German, good English. Arrangement: Part time; hybrid; weekly office required and team normally meets>=3 times/week; REF2835O.

#### ML05: SAP — Working Student (f/m/d) - AI-Enhanced Optimization & GPU Computing

[Official description](https://jobs.sap.com/de/stellen/744000159962909/working-student-fmd-ai-enhanced-optimization-gpu-computing/) · Walldorf · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer/ATS description accessible; apply link accessible unless noted
Responsibilities: Develop classical planning/logistics optimization algorithms; Develop/evaluate learned heuristics and prediction models; Prototype/benchmark GPU solver approaches
Candidate requirements: Python; One optimization framework; Optimization or ML or algorithm foundations; Reproducible experiments; Rigorous analysis/documentation
Preferred: CUDA/cuOpt; PyTorch/scikit-learn; C++; OR decomposition
Enrollment: Currently enrolled CS/math/physics/operations research. Language: Not specified. Arrangement: 20 hours, flexible scheduling; hybrid; REF2883A.

#### ML06: menio — Werkstudent (m/w/d) Machine Learning/Computer Vision

[Official description](https://menio.jobs.personio.de/job/2869223) · Hannover / remote · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer/ATS description accessible; apply link accessible unless noted
Responsibilities: Compare few-shot and visual-similarity approaches; Build documented real-world food dataset and benchmarks; Robust/open-set recognition and cross-location tests; Define evaluation metrics and test scenarios
Candidate requirements: Python projects; ML/deep-learning fundamentals
Preferred: PyTorch; Classification/embeddings/detection experience
Enrollment: CS/Data Science/math or similar current study. Language: Not specified. Arrangement: HeaderparttimeWerkstudierende; flexible/remote. Benefits boilerplate also says part/fulltime; student role counted based on explicittitle/header.

#### AI08: plusserver — Werkstudent:in KI / AI Infrastructure (m/w/d)

[Official description](https://karriere.plusserver.com/Werkstudentin-KI-AI-Infrastructure-mwd-de-j929.html) · Dresden / Hamburg / Köln (employer current vacancy listing) · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer/ATS description accessible; apply link accessible unless noted
Responsibilities: LLM performance/load/quality/resource tests; Configure inference servers, proxies, API gateways and frontends; Integrate MCP tools; Automate deployment/operations and document/monitor systems
Candidate requirements: Linux/Unix basics; Scripting e.g.Python or Bash or Go; Interest in LLMs/infrastructure/DevOps/MCP
Preferred: Cloud/virtualization experience (AWS/Azure/GCP)
Enrollment: Current technical degree. Language: Very good German and English. Arrangement: Homeoffice possible; currentlisting sayshybrid.

#### ML07: GPI Consulting — Werkstudent im Bereich Machine Learning & KI (w/m/d)

[Official description](https://jobapplication.hrworks.de/de?companyId=aid11b25&id=f3a81a) · Hamburg / homeoffice · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer/ATS description accessible; apply link accessible unless noted
Responsibilities: Design/implement AI solutions; Select/fine-tune/integrate ML models
Candidate requirements: Computer vision; Hugging Face/Transformers; Docker; Python; TensorFlow; NumPy; Initial software development/architecture experience
Preferred: Java/.NET/JavaScript
Enrollment: At least3rd bachelorsemester or master predominantly CS/math. Language: Very good German, ideallyC1. Arrangement: Part timeWerkstudent; remote first/hybrid.

#### ML08: dida — Machine Learning Working Student (all genders) - Hybrid, Berlin

[Official description](https://dida.jobs.personio.de/job/239760?language=en) · Berlin · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full official employer/ATS description accessible; apply link accessible unless noted
Responsibilities: Applied CV/NLP/ML research and industry products; Develop projects/products with ML experts
Candidate requirements: Very good grades in mathematical subjects; Interest in applied statistics; Interest in programming Python/Julia or similar; Interest in modern ML/deep learning
Preferred: None explicitly separated
Enrollment: Studyingmath/physics/CS. Language: Not specified. Arrangement: 15–20 hours; hybrid; plan toremainBerlin>=1.5years.
Coding note: Profile asks interest in applied statistics and programming Python/Julia or similar, not demonstrated Python mastery.

#### DS02: QuoData GmbH — Working Student – Data Scientist (m/f/d)

[Official description](https://download.quodata.de/en/node/59) · Dresden, Germany · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full employer description accessible; active application instructions; no closure notice
Responsibilities: Statistical client analyses, agentic data/model/report workflows, web software and automation.
Candidate requirements: Current technical/quantitative studies; Python; Git including branches, pull requests and merge conflicts; Practical AI-tool use with critical checking; Interest in statistics; Lives in/near Dresden; 10–20 h/week; Very good English
Preferred: SQL; pandas/NumPy/R; FastAPI/Django/JavaScript framework; Docker; CI/CD; German
Enrollment: See candidate requirements. Language: See candidate requirements. Arrangement: Not specified; requires living in or near Dresden.
Coding note: Page metadata mentions internship but full heading/profile explicitly Working Student, paid hours10–20; thesis only optional. AI-assisted coding/use is not counted as an LLM-engineering skill; generic statistical experiments or AI-output review are not counted as model evaluation.

#### DS03: RTE Akustik + Prüftechnik GmbH — Werkstudent:in Data Science / KI (m/w/d)

[Official description](https://www.rte.de/de/ueber-uns/karriere/werkstudent-data-science/) · Pfinztal, Germany · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full employer description accessible; application instructions; no closure notice
Responsibilities: Acoustic signal preparation/features; classifiers, anomaly detection and model validation against industrial quality requirements; reproducibility.
Candidate requirements: Current quantitative/technical studies; Python; Reproducible work using Git and virtual environments; 12 months remaining studies; 15–20 h/week
Preferred: NumPy; scikit-learn; PyTorch
Enrollment: See candidate requirements. Language: Not specified. Arrangement: Home-office option.
Coding note: AI-assisted coding/use is not counted as an LLM-engineering skill; generic statistical experiments or AI-output review are not counted as model evaluation.

#### DS04: Cogitaris GmbH — Werkstudent (m/w/d) im Bereich Data & Technology

[Official description](https://cogitaris.de/karriere/werkstudent-data-technology) · Mainz, Germany · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full employer description accessible; live application form; no closure notice
Responsibilities: ETL pipelines, REST APIs, text/forecasting ML models, interactive dashboards and process automation.
Candidate requirements: Current relevant studies; First experience Python OR R OR JavaScript/TypeScript; Interest in databases/cloud/tools; Good German and English
Preferred: None explicitly separated
Enrollment: See candidate requirements. Language: See candidate requirements. Arrangement: Home-office option.
Coding note: AI-assisted coding/use is not counted as an LLM-engineering skill; generic statistical experiments or AI-output review are not counted as model evaluation.

#### DS05: Vodafone — Werkstudent Data Science mit Schwerpunkt Network Analytics (m/w/d)

[Official description](https://opportunities.vodafone.com/job/M%C3%BCnchen-Werkstudent-Data-Science-mit-Schwerpunkt-Network-Analytics-(mwd)-in-Unterf%C3%B6hring-(Lkrs_-M%C3%BCnchen)-Baye/579062501/) · Unterföhring (Landkreis München), Germany · checked 2026-11-16 · source date: 2026-11-05

Status: Full employer description accessible; apply links; no closure notice
Responsibilities: Exploratory/predictive network and customer-experience analysis, classification/clustering/pattern search, Python and early GenAI network analysis.
Candidate requirements: Relevant technical studies; Statistics; Python; Interest in ML/deep learning/GenAI; Fluent German and English; Current enrollment certificate
Preferred: First Data Science or ML experience
Enrollment: See candidate requirements. Language: See candidate requirements. Arrangement: Full Flex Office by agreement.
Coding note: AI-assisted coding/use is not counted as an LLM-engineering skill; generic statistical experiments or AI-output review are not counted as model evaluation.

#### DS06: Tegtmeier Internet Solutions GmbH — Werkstudent:in Data Science (m/w/d)

[Official description](https://join.com/companies/sinnkontorde/16943011-werkstudent-in-data-science-m-w-d-tegtmeier-internet-solutions) · Hamburg, Germany · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full authorized employer ATS description accessible; apply button; no closure notice
Responsibilities: Data preparation/quality, hypotheses and statistical checking, A/B experiments, dashboards, deployment and monitoring, explaining findings and limits.
Candidate requirements: Enrolled in related studies; Python and R; Git and readable code; SQL database basics; Visualization, experiment design and statistics; Daily AI-assisted coding; German C1; English B2; 20 hours/week
Preferred: Tutoring experience
Enrollment: See candidate requirements. Language: See candidate requirements. Arrangement: 3 days/week on site; 12 month contract.
Coding note: AI-assisted coding/use is not counted as an LLM-engineering skill; generic statistical experiments or AI-output review are not counted as model evaluation.

#### DS07: 1KOMMA5° — Werkstudent:in Data Analytics (Controlling Focus) (m/w/d)

[Official description](https://join.com/companies/1komma5grad/16913623-werkstudent-in-data-analytics-controlling-focus-m-w-d) · Hamburg, Germany · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full employer ATS description accessible; apply button; no closure notice
Responsibilities: End-to-end finance pipelines, forecast datasets and KPI reporting, Looker dashboards, data integrity, AI analytics for forecasts/anomalies.
Candidate requirements: Enrollment at German university for at least two further semesters; 15–20 hours/week; SQL and Python; Large-dataset ingestion/transformation/modeling experience; Very good German and English (C level)
Preferred: Git; BI tools e.g. Looker/Power BI/Tableau; AI or ML e.g.predictive models and forecasting; Finance/controlling interest
Enrollment: See candidate requirements. Language: See candidate requirements. Arrangement: Text offers Hamburg office and/or remote; ATS location metadata says on-site; agreement needs checking.
Coding note: AI-assisted coding/use is not counted as an LLM-engineering skill; generic statistical experiments or AI-output review are not counted as model evaluation.

#### DS08: DRM Datenraum Mobilität GmbH (Mobility Data Space) — Werkstudent Data Analytics (m/w/d), Kennziffer 2025/17

[Official description](https://mobility-dataspace.eu/de/karriere) · Munich, Germany · checked 2026-11-16 · source date: No exact publication date displayed

Status: Full description under official Open Positions; active application instructions; no closure notice
Responsibilities: Automated usage analysis, data-based applications, combining sources, large data and real-time analytics.
Candidate requirements: Related current studies; Analytics/BI/visualization experience or strong interest; Excel OR SQL OR Python; Data modeling/preparation understanding; Very good German and English
Preferred: ML or statistical analysis; Cloud e.g.Azure/AWS/GCP; Git or REST/asynchronous API experience
Enrollment: See candidate requirements. Language: See candidate requirements. Arrangement: Flexible remote work and hours.
Coding note: AI-assisted coding/use is not counted as an LLM-engineering skill; generic statistical experiments or AI-output review are not counted as model evaluation.

### Exclusions

Search results were insufficient when the actual page was expired, missing, unreadable or blocked.
- [https://careers.telekom.com/de/jobs/werkstudentin-ai-inference-platform-engineering-m-w-d-x-733424](https://careers.telekom.com/de/jobs/werkstudentin-ai-inference-platform-engineering-m-w-d-x-733424): Search result promising but full description returned 403 on direct open; not counted
- [https://jobs.smartrecruiters.com/KOSTALGroup/744000098293096-werkstudent-fur-machine-learning-operations-m-w-d-ka-](https://jobs.smartrecruiters.com/KOSTALGroup/744000098293096-werkstudent-fur-machine-learning-operations-m-w-d-ka-): Full text accessible but explicit expired-job button, excluded
- [https://flex-capital-management-gmbh.jobs.personio.de/job/2479397](https://flex-capital-management-gmbh.jobs.personio.de/job/2479397): Search snippet looked active; direct official description returns404, excluded
- [https://ag.wd3.myworkdayjobs.com/de-DE/Airbus/job/Werkstudent-fr-Scientific-Computing---Machine-Learning--d-m-w-_JR10414181](https://ag.wd3.myworkdayjobs.com/de-DE/Airbus/job/Werkstudent-fr-Scientific-Computing---Machine-Learning--d-m-w-_JR10414181): No readable full description on direct open; search snippet not counted
- [https://www.rohde-schwarz.com/ch/karriere/stellenangebote/werkstudent-in-machine-learning-operations-m-w-d_251563-1628190.html](https://www.rohde-schwarz.com/ch/karriere/stellenangebote/werkstudent-in-machine-learning-operations-m-w-d_251563-1628190.html): Direct officialdescription410Gone
- [https://jobs.sap.com/job/St_-Leon-Rot-Working-Student-%28fmd%29-Machine-TranslationNatural-Language-Processing-68789/1437176333/](https://jobs.sap.com/job/St_-Leon-Rot-Working-Student-%28fmd%29-Machine-TranslationNatural-Language-Processing-68789/1437176333/): Redirects togeneraljobsearch; no fullposting
- [https://join.com/companies/dataventio/16877977-working-student-ai-engineering](https://join.com/companies/dataventio/16877977-working-student-ai-engineering): 410Gone
- [https://jobs.siemens-energy.com/en_US/CareersMarketplace/FolderDetail?folderId=297762](https://jobs.siemens-energy.com/en_US/CareersMarketplace/FolderDetail?folderId=297762): 406NotAcceptable
- [https://kiwigrid.jobs.personio.de/job/2327992](https://kiwigrid.jobs.personio.de/job/2327992): 404notfound

Additional excluded descriptions: expired Vattenfall, unavailable Mercedes/SAP, filled EnBW, JOIN410 solutions4performance, unreadable Sartorius.

### Project implication (inference from this sample)

Keep the project focused on Python, SQL, reproducible data/model work, Git and clear evidence. Show temporal model evaluation, strong simple baselines, documented experiments, data-quality checks and a readable explanation of limits. For AI roles, foreground the existing structured outputs, fixed test set, failure examples and cost/latency measures, then improve their grounding evidence throughR15/R16. Docker and one deployable API are useful delivery evidence. The sample does not justify adding Kubernetes, Airflow, MLflow, LangGraph and cloud infrastructure all at once. Several already exist here as CI demonstrations and should be described with that scope. Statistical analysis and enrollment/language constraints remain important, especially DS roles.

### Requirement-to-project and candidate evidence

| Hiring requirement | Project already demonstrates | Gap to close / evidence path | What remains candidate-specific |
|---|---|---|---|
| Python/software quality | Typed package, tests, CLI, API, CI | FixR01/R02/R10; short code tour with one reproducible failure and regression | Owner can explain and independently modify chosen code; do not infer this from generated source. |
| SQL/data preparation | DuckDB, Parquet, dbt, pandas/Polars notebook | Repair SQLboundary; show one data-quality investigation and consistent eligibility query | Personal query/statistical reasoning demonstration. |
| Classical ML/statistics | Quantile boosting, calibration, walk-forward comparisons, uncertainty | ML explanation/prospective evaluation, meaningful baseline and limitations before stack list | Ability to explain leakage, calibration, paired populations and bootstrap choices. |
| AI/LLM engineering | Plain/context/tool/graph agents, fixed eval, JSON, tracing/budgets | R03/R04 visibility, R15 comparable metrics, R16 grounding; one trace with a real failure case | Owner-led evaluation labels/interpretation; code review skills when using AI. |
| Delivery/MLOps | DockerAPI, registry, promotions, CI, live scheduled publication | R06/R07/R08/R09; distinguish hosted core from kind/DAG demonstration | Deployment/debugging contribution and explainable tradeoffs. |
| Communication/domain analysis | Methods, public cards, honest losing results | Add short owner-written analysis and two-minute walkthrough; link artifacts instead of every library | Approved personal narrative, language proficiency and examples. |
| Enrolment/time/location/language | Portfolio cannot establish these | Profile fields with approved facts; target relevant postings | University/degree, remaining study duration, start/hours, German/English, commute/remote constraints. |
| Specialized CV/GPU/Databricks/domain tools | Some reusable ML/data foundations | Treat as role-specific gaps when applying, not a reason to bolt every stack onto forecasting | Independent experience may exist elsewhere; ask before claiming absence or mastery. |

## E. Hiring presentation and disciplined stack plan

### E1. Primary route and first-screen specification

Use `recruiters.html` for applications, homepage for the public benchmark, and the GitHub About website link for a direct route to the recruiter page. Sitewide navigation must expose both. The recruiter screen should have this reading order:

1. **Jashdeep Singh** + target **Werkstudent AI / Machine Learning / Data Science**, with the target adjusted to the application rather than three equal competing pitches.
2. One sentence explaining the public forecasting benchmark and the relevant capability.
3. One compact verified proof card: backtest period/sample/baseline/result and direct methodology link.
4. Primary action **View the evidence**; secondary **Contact / CV** only when approved working destinations exist. Until then use **Read the code**. Do not publish placeholder actions.
5. Short observed operational state and AI-assistance/contribution disclosure, with deeper detail immediately below.

At desktop 1366×768 use a concise left candidate/purpose/actions column and right proof chart. At390×844 and390×700 place name/role, short purpose, proof and actions in one column before activity counts or an empty leaderboard. Keep numbers legible, contrast/focus states clear and no decorative hero image. A real backtest comparison graphic is useful; generic neural-network artwork is not evidence. First-screen proof can be a small static SVG generated from the same cards. Do not claim a10second outcome until tested with readers.

Draft English copy, subject to owner-approved profile and contribution details:

> **Jashdeep Singh · Seeking a Werkstudent role in AI / Machine Learning**  
> Python forecasting, evaluated in public.  
> Forecast Arena compares classical models and LLM agents using forecasts published before outcomes are known.  
> **Electricity backtest: Brier 0.1930 vs 0.2466 for the base rate.** 365 days,2,190 questions; paired difference −0.0536,95% day-block interval [−0.0655,−0.0414].  
> **View the evidence** · **Read the code**  
> AI-assisted development. See the contribution breakdown and current live status below.

This copy uses an existing verified project result. It does not assert a degree, employment eligibility, fluentGerman, solo implementation or liveMLsuperiority. A shorter visible proof may show only two scores plus “365-day backtest”, with sample/interval on the linked card. “21.7% lower Brier” is mathematically different from“21.7% more accurate”; prefer the original score/difference.

Draft German copy, with native proofreading pendingH17:

> **Jashdeep Singh · Auf der Suche nach einer Werkstudentenstelle im Bereich KI / Machine Learning**  
> Prognosen mit Python entwickeln und nachvollziehbar bewerten.  
> Forecast Arena vergleicht klassische Modelle und LLM-Agenten anhand von Prognosen, die vor Bekanntwerden des Ergebnisses veröffentlicht werden.  
> **Strompreis-Backtest: Brier-Score 0,1930 gegenüber 0,2466 für die Basisrate.** Zeitraum:365 Tage;2.190Fragen.  
> **Ergebnisse und Methode ansehen** · **Code ansehen**  
> Mit Unterstützung von KI-Coding-Agenten entwickelt. Eigene Beiträge und aktueller Betriebsstatus sind unten dokumentiert.

Draft README opening:

> # Forecast Arena  
> Public forecasting benchmark comparing classical ML and LLM agents, with an append-only record and forecasts published before outcomes.  
> **By Jashdeep Singh · AI-assisted project · Werkstudent portfolio**  
> **[Recruiter overview](https://jashd12.github.io/forecast-arena/recruiters.html)** · **[Live benchmark](https://jashd12.github.io/forecast-arena/)**  
> **365-day electricity backtest:** Brier 0.1930 versus base-rate 0.2466, with a supported paired difference. [Model card and limits](https://jashd12.github.io/forecast-arena/backtests.html#card-power).  
> Live results remain in rehearsal. Model, prompt and operational evidence is linked below.

The model-card anchor `card-power` was verified in the inspected build; recheck it if the generator changes. Put one compact real figure after this opening; move large stack/skills/results tables below or into existing details. `scripts/readme_sections.py` owns generated blocks; change the producer/shared evidence definitions rather than hand-editing generated text. Keep existing honest authorship disclosure prominent enough to find.

### E2. Page-by-page implementation

| Surface | Concrete change | Evidence / completion requirement |
|---|---|---|
| Recruiters | Candidate hero; one result; role paths; approved profile/contact; concise contribution block | Above-fold checks +actual model card/eval/trace links; no unknown details rendered. |
| Homepage | Shorten abstract; first visible evidence; direct recruiter action; compact current participation | Preserve today's forecasts and true operational state; no empty headline table as main selling point. |
| README | Concise opening, one image,3proof bullets; details for full stack; current domain/schedule text | Edit generator too; `--check`; scopes and evidence match site. |
| GitHub About | Prepared description, recruiterURL, selected topics; owner pinning/preview | Owner action separately verified; cannot alter native file-list layout throughrepoCSS. |
| German | Equivalent candidate/purpose/proof/actions, accurate Englishlink, approved personal facts | Proper `lang`, language switch, H17 proofreading pending until real review. |
| About | Consistent contribution narrative and professional contact | Do not repurpose a legal postal address as recruitment content. |
| Questions | Universal status, ML method, actual graph traces and links to samples | R03/R04 exact reported case and other families. |
| Leaderboard/topics/profiles/calibration | Published/pending/scored/eligible states; full roster + clearly scoped scores | R03/R05; no fabricated rank/score or changed headline protocol. |
| Backtests/Experiments | Keep losses; clear evaluated vs promoted artifacts, dated diagnostics | R06/R17; no model tuning to improve appearance. |
| Evals/LLM | Comparable pinned evidence; observable failures; sample policy | R15/R16; no misleading before/after causality. |
| Stack/Methods/Status/Data/API | Clear deployment scope, per-domain versions, current schedules, finalrunstate and robust mobile paths | R02/R05/R07/R11/R13; generated schemas/docs. |
| Play | Preserve simple working interaction and no-JS fallback | Game results/reveal use real fixture/live data; no fabricated social proof. |

GitHub metadata package ready for the owner to apply:

- **Description:** “Public forecasting benchmark comparing classical ML and LLM agents. Python pipelines, time-aware evaluation, model promotion and an append-only forecast record.”
- **Website:** `https://jashd12.github.io/forecast-arena/recruiters.html`.
- **Topics:** `forecasting`, `machine-learning`, `llm`, `time-series`, `python`, `model-evaluation`, `mlops`, `data-science`, `langgraph`, `duckdb`. Keep only topics still represented by maintained evidence.
- **Pin:** repository on the owner's profile; link from approved CV/LinkedIn/project entry.
- **Repository social image:**1280×640, solid background, under1 MB, showing project name, concise purpose and clearly labeled proof. GitHub recommends this best-display size; keep the website's separate1200×630 asset where appropriate. [Official guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview).

### E3. Candidate-led proof work

These are proposed demonstrations, not completed personal achievements. Let the owner select a small number and document exactly what they did:

- Explain and independently reproduce one defect, write its regression and walk through the fix, e.g.finite-number validation. Record a short code walkthrough with command/results.
- Produce a short DS analysis of one fixed dataset: baseline comparison, paired population, uncertainty, missingness and limitations. Explain why a favorable tiny sample is insufficient.
- Label a small frozen LLM-grounding set, review disagreements and summarize failure modes. Explain JSON compliance versus factual grounding versus forecast quality.
- Demonstrate loading one saved model in a fresh process, trace its inputs/as-of cutoff and published probability, and explain why another family lost.

Do not fabricate a STAR story claiming the owner personally implemented an agent-written subsystem. A contribution table should separate owner specification/decisions, personally verified work, AI-generated implementation and collaboration/review. Missing evidence is not proof the owner lacks the skill; it is a request for observable evidence.

### E4. Retain / improve / add / defer

| Decision | Problem/gap and simpler alternative | Benefit / acceptance | Effort and maintenance / opportunity cost |
|---|---|---|---|
| **Retain** Python, Jinja, CSS, smallJS, Actions/Pages/fileledger | Core site works; no framework bottleneck measured | Fast reproducible static proof with existing tests | Lowest maintenance; preserves time for correctness and candidate evidence. |
| **Improve** shared participation/provenance views | Missing-state confusion; existing typed records already contain much evidence | R03–R05 exact outcomes; one source for allpages/API |2–4 days combined, coordinated ownership; avoid duplicating counts in templates. |
| **Improve** existing DuckDB/typed validation boundaries | ConfirmedR01/R02; use engine parsing and existing schema stack first | Malformed inputs and writes refused |1–2 days combined; no separateDBservice needed. |
| **Improve** model/eval evidence | Existing diagnostics/LLM highlight need scope and comparable definitions | R15–R17; model details agree with saved forecasts |1–4 days selected scope; more valuable than another model family. |
| **Improve** existing CI/incident/dependency handling | Green can coexist with advisory findings; deployment failures need alerts | R07/R08 complete final outcome and triage |1.5–3 days; maintain narrow environmentgroups. |
| **Add, justified** optional typed inference-explanation artifact | Existing hashes cannot explain numeric probability conversion | Future pre-lock diagnostics reproduce publishedP |2–4 days; existingstorage/UI/schema, no paidLLMservice. |
| **Add, owner gated** bounded external morning trigger | Repeated late scheduler starts threatenlock | Real futurepre-lockrun without manualrescue |Owner setup+0.5–1daycode/docs; credentialcare and monitoring. |
| **Retain with explicit scope** FastAPI/Docker, dbt/notebook, MLflow/drift | Useful existing proof, some only demonstrated inCI | One clear runnablepath each, namedexactly |Maintenance already incurred; do not advertise publichosting thatdoesnotexist. |
| **Defer** public dashboard hosting, players, crypto | Optional owner tasks not necessary for next hiring improvement | Revisit H19/H15/H12 only when genuinelyneeded |Avoidaccounts/privacy/licensing/datauptime work overshadowing coreproof. |
| **Defer** Airflow/Kubernetes expansion, vectorDB, newcloud, frameworkrewrite, largerLLM, anotherfoundationmodel | No demonstrated need from current workload or sample | Require a specific usecase, simpler alternative failure and successmeasure |Potentially days/weeks+ongoingcost; current candidate proof is higherreturn. |
| **Optional role-specific extension** computer vision/GPU/Databricks | Some postings require specializedexperience not demonstratedhere | Small separate role-specificexercise if owner targets thosejobs |Do not distort a coherent forecasting project to cover everyposting. |

## F. Ordered implementation backlog and ownership

The details, tests and definition of done for each task are inR01–R17. This table assigns sequence and shared components so another agent can begin without repeating the audit. Assign new repository taskIDs after checking current `TASKS.md`; RIDs here are audit references, not fabricated completed tasks.

| Order / work package | Findings / owner | Files and dependencies | Deliverable / verification gate |
|---|---|---|---|
|0. Snapshot and baseline | Integrator | Read AGENTS/SPEC/TASKS/DECISIONS, cleanstatus/current refs/current runs; preserve newerwork | Revalidate only changed assumptions, recordSHA; no duplication of repairedF1–F9. |
|1a. Numeric integrity | R01, integrityowner | models.py, parsers/domainbase/resolution, serializer/store tests | New regression failsbefore fix, strictfinite/noNaNappend, existingdomain/E2E pass. |
|1b. Query consistency | R02, APIowner | mcp_server.py, api/app.py, tests | Can run parallel1a; typedread-only SELECT boundary and immutablecounts. |
|2a. Shared participation contract | R03, viewowner | New/displaymodule +build/shaping/profiles/topics/API | Complete per-question and per-scope statuses; API additive compatibility; tests before templateintegration. |
|2b. Ops monitor/dependencies | R07/R08, opsowner | workflow_evidence,health,cli/record,ci.yml,requirements | Parallel2a; no sameworkflow file edits bymultiple owners; final-stage alert tests and isolatedruntimeinstalls. |
|2c. Scheduling preparation | R09, opsowner +human | morning/weekly/sharedconcurrency/runbook/H20proposal | Depends on revieweddispatchpolicy; ownerconfig prepared, realacceptance remainsfuture. |
|3a. Model and question UI | R03/R04/R05/R06, viewowner | Templates,per-domain inventory,trace/status links | Depends2a; targetpage+all family/state fixtures; promotionlabel corrected; all links valid. |
|3b. Hiring profile/proof contract | R12/R15, contentowner +human | Approvedprofile,evidencecomparisondefinition,recruiters.py,READMEgenerator | Can startafter0; no inventedfacts; sharedresultsource finalized beforecopyvariants. |
|3c. Mobile shell and hiring layout | R12/R13/R14, frontendowner | base.html/style.css,home/recruiter/DE/metadata | Consume view/proof contracts; oneowner integrates CSS/base changes; responsive/keyboard/without JavaScript/print checks. |
|3d. Docs/CLI cleanup | R10/R11, integrator | cli/jobs.py,runbook/spec/status/READMEgenerators,progress/tasks | Currentcommands/schedules and Nov 16liveacceptance documented; generatedchecks. |
|4a. Future explanation capture | R04, modelowner | ml.py/familymodules/typeddiagnostic/persistence | Only afterR01 boundary and explanationcontract; preserve probability, appendnewrecordsbeforelock. |
|4b. Evaluation quality | R16/R17, DS/AIowner | evalharness,frozenfixtures,weeklydiagnostics/reportmetadata | Separateformat/grounding/forecast metrics; disjoint heldout evidence; ownerinterpretation. |
|5. Optional extras | E4 deferreditems, humanprioritizes | Separateproposal | No automaticmigration/service/model addition. |
|6. Integration, staged release and naturalrun evidence | Integrator | Allchecks/generatedartifacts/CI/deploy/realread-onlyacceptance | G below; finalreport lists pass/fail/pending withrun/SHAs. |

Shared-file rules: integrityowner owns `models.py` and canonical serializer; viewowner owns participant schema, `site/build.py` and API viewshape; contentowner owns shared proof definition and README producer; frontendowner owns base/style after agreeing markup; opsowner owns YAML and dependency locks. Other agents send scoped patches rather than editing those files concurrently. Modelowner consumes the agreed explanation contract before changing familyinterfaces. Integrator reviews cross-boundary behavior and merges in dependency order.

The early useful milestone is R01/R02 plus basic R03/R04/R05, not completion of all optional diagnostics. Hiring pages can progress in parallel after approved facts and proof data exist. Estimates overlap and should not be summed as a guaranteed calendar duration.

## G. Verification, operational evidence and rollout

### G1. Recent Actions and issues checked

All11 workflow definitions were inspected, with100recent repository runs plus latestfiveperworkflow where available, representative older failures and openissuehistory. Runattempt1 is the default for references below unless a source explicitly identifies a retry. Old red runs remain historical evidence. At the16Novrefresh there are **no open issues**; issue 2 closed after the successful morning. This does not establish absence of the new defects found locally.

| Workflow | Run/job/stage evidence | Finding / current conclusion |
|---|---|---|
| morning | [43816839671](https://github.com/JASHD12/forecast-arena/actions/runs/43816839671): gate133130706274, application133130898711, deploy133136694814 allsuccess; deploysmoke passed | Actual33 ML+4graph forecasts, complete264forecast-or-skip pairs; sealbeforelock. Eventmain, executedb072stablecode. Earlier43726015740 greenno-op becausebatchalreadysealed, notanotherforecastpublication. |
| evening | [43760526246](https://github.com/JASHD12/forecast-arena/actions/runs/43760526246), application132954240440; deploy132954549446 | Published33 questions forbatch16/target 17; failedfinalhealth because immutablebatch15lackedML; deployandsmokesucceeded. Correct historical-gap alert. |
| resolve | [43820295182](https://github.com/JASHD12/forecast-arena/actions/runs/43820295182), finalsuccess at06:58:03 UTC | Successful latestresolve/deploy; older[43739003408](https://github.com/JASHD12/forecast-arena/actions/runs/43739003408) application 132888144021 historicalcoveragefailure and deploy132888396274 environmentrejection; main retry43739259441 deployed successfully while retaining truthful healthfailure. |
| weekly | [43695904785](https://github.com/JASHD12/forecast-arena/actions/runs/43695904785), job 132756252618 | RealSundaypublication: attentionLightGBM n224,Brier 0.1053; powerHGB n168,Brier 0.1395. These are weeklyevaluation, not liveaccuracy. Old43499775264 wasdry run. Old43263435028 failedtrajectoryvalidation, latertrainingrunsucceeded. |
| players |43735157229, gate132876009373 | Afterlock, runskipped; unconfiguredownerintakeH15. Green doesnotproveactualplayers. |
| workflow-evidence |43760722179, job 132954699894 | Successful observerappend; historicalmissingexecution evidence stillblocks oldclean days. R07finalinstantalerting remainsgap. |
| ci | [43740896689](https://github.com/JASHD12/forecast-arena/actions/runs/43740896689), check132893600562,inference132893600951,audit132893600957 | Eightjobssuccess; actualtestcounts inB4; auditfindingsR08. Old43451887481k8srolloutfailed due service-linkenv collidingwithstrictsettings; current kind passesafterfix. |
| promote | [43741816243](https://github.com/JASHD12/forecast-arena/actions/runs/43741816243) | Stablepromoted tob072afterpassingpushCI; skippedpromotes afterfailed/cancelledCIareexpected. |
| llm-eval |43536831332 and43536827673 | Successful frozenoffline-question evaluations14Nov; runtimes/config compareseparately. No auditpaidrerun. |
| llm-smoke |43294520796, job 131449149179 | Existingrealproviderresponses; neither accuracyproof nor newauditcalls. |
| deps |43263909444, job 131342218873 | Monthlyreportworks; nextscheduleddate not yet due; no dependencyissuecreationpendingH11. |

Issue2 closure [comment6909434024](https://github.com/JASHD12/forecast-arena/issues/2#issuecomment-6909434024) reports the new healthy batch. Issue1 was a closed deliberate forced-health test. Old invalid-workflow runs43581416348/43581415464/43581414464 were GitHubexpression-comment syntax errors already fixed with workflow-syntax regressions. Do not plan to fix those again. Cancelledweekly43498831026 had no jobs; exact cancellationcause was not fully verified, so label it unknown rather than asserting concurrency from appearance alone.

GitHub's current concurrency documentation confirms that defaultpending work may be replaced and describes optionalqueuebehavior. Assess it against the morningdeadline; do not reflexively queue100longrunningjobs. [Official concurrency documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

### G2. Implementation verification sequence

1. Pin source and read-onlyledger snapshot; record current source/dependency versions and relevant runIDs. Read current operatinginstructions and preserve dirtywork. Recheck whether any Rtask has already been completed since this snapshot.
2. ReproduceR01/R02 in disposable fixtures and write meaningful boundary regressions. Run affected parser/domain/record, MCP/REST and serializer tests first. Never exercise mutation payloads against a remotely hosted productionservice.
3. Exercise the shared participant/explanation view with fixture times **before morning**, **after forecasts but before resolution**, **after resolution**, **after lock**, and **with a void/revision**. Assert precise statuses, model hashes, sampling links, no fabricatedscores and no changed canonicalpopulation.
4. For prospective explanation capture, run weekly→registrypublication→newinterpreter→productionfactory→morning→seal→verify→idempotentretry. Use HGB/LightGBM/PyTorch under actual inference dependencies, not a trainingextras environment masking imports. Cover empty/corrupt/future artifact and one-domainfailure. Assert probability equality and old sealed bytes unchanged.
5. Run appropriate existing full checks after integration: `make check`, `make site-e2e`, `make a11y`, notebook/dbt checks for affected exports, MCP/API tests, `scripts/readme_sections.py --check`, and badgechecks with realcoverage/JUnitXML. Use existing separately constrained dependencyenvs. Review real testcounts/skips; report environment failures honestly.
6. Build with empty/fixture/currentread-onlyledger data. Linkcheck all generatedpages/assets/anchors; validate JSONschemas and additivecompatibility. Inspect reportedquestion, oneactualgraphsample, all fourMLfamilies and error/not-sampled/pending/resolved/legacy-missing states on desktop/mobile. Review print output and without JavaScript, actualfocus/menu/tab/tableinteractions; fix inlineoverflow without removing usefuldata.
7. Collect a bounded browser loading trace/Lighthouse if tooling isavailable; report viewport/network/throttling and labversusfieldlimits. No invented performanceimprovement. The small existingfrontenddoesnotneedarewrite to satisfy thischeck.
8. For a later authorizedrelease, commit reviewedwork in task-sizedchanges, require CI for exact SHA, inspect stablepromotion and deployref policy, deploy through existingprocess and verify smokeagainstactualpublicoutput. This audit itself doesnotauthorize remotechanges; the executingagent follows its actualuserauthorization and repositoryrules.
9. Inspect the next natural resolution after eachdomain's `resolve_after`; powerday-ahead batch 16/target 17 is firsteligible **16Nov12:30 UTC (13:30Berlin)**. Weather/attention/currencies follow their own rules, not that powerdeadline. Verify genuineoutcome→canonicalscore→SQL/dbt/Parquet/API/HTML agreement and thenMLvisibility. Check graph onlyonitsactualsample; retainunansweredstatesuntilsourcesarrive.
10. On later naturalmorning batches verify completeexpectedpairs, realMLprobabilities, boundedgraphsample, version/artifact/asofmetadata andpre-lockcommit. A futurequalifyingweeklypromotion mustchange subsequentinference and leave oldforecasts untouched. Fivecompletedcleandays/officialnot-before acceptance is separate and mustwaitforreal calendar evidence.

Rollback: revert frontend/code changes through normal reviewed commits and CI, preserving ledger history. Optional presentation/enhancement modules may be disabled with honestavailability labels. Do not “rollback” by deleting records, retraining to fitliveanswers, backdating forecasts, insertingoldskips, loweringhealthcriteria or setting an earlierofficialdate. If new diagnosticsfail, preserve a validforecast and publishdiagnosticunavailability; actualunsafeinference canbe disabled prospectively with explicit skips and incidents.

### G3. Remaining gates and owner actions

| Gate | Can complete now? | Evidence required to close |
|---|---|---|
| First real ML daily registration | **Already satisfied** in inspected batch |33/33 forecasts, fourdomains, pre-lockseal, correctversions; reconcile datedT057/T193e documentation. |
| First real ML scoredoutputs | Future naturalresolution | Actualsourceoutcomes and samepopulation score/export/UI agreement; no artificialtestoutcomes inliveledger. |
| RepeatMLcoverage and laterchampionreplacement | Future scheduledcycles | Subsequentbatch and qualifyingpromotion run/artifacts/versionchange. |
| Final-workflow alerts | Can implement/testnow | Mockedfailure/recoverytests; lateractualdeploymenthealth evidence whennaturally available. |
| SchedulerH20 | Preparationnow, setupowner | Owner-heldcredential/service, firstnaturallytriggeredpre-locksuccess. |
| Candidatehero/contact/ownership | Draftnow; factsowner | Approveddegree/enrolment/languages/hours/start/location/links/contributions. Hideunknowns. |
| GitHubsettings/H18, GermanH17 | Packagenow; owneraction | Actuallyappliedmetadata/pin/preview; actualnativeproofreading. |
| Officialstart | Future+ownerdate | Fiveconsecutivecompletecleandays+not-before; currentfallback2099-12-31 doesn't establish actualprivatevariablevalue. |
| Players/crypto/dashboard | Optionalownerfollowup | H06/H15,H12,H19; notprerequisites for truthfulcorehiringpage. |
| Humancomprehension | Protocolnow; realpeoplelater | Realresponses underH; leavependingwithoutreaders. |

## H. Ten-second human comprehension test

Recruit3–5 people unfamiliar with this project; do not pretend an agent simulation is humanfeedback. Show one of the five entrypoints for10 seconds, then hideit. Counterbalance order or use different readers so earlierpagesdo not teachlateranswers. Test desktop andphone with at leastone ofeach; include primaryrecruiterpage, rootwebsite, GitHubnative landing, READMEopening and sharedpreview separately wherefeasible.

Ask, without leading:

1. Who is the candidate and what role are they targeting?
2. What does the project do?
3. What result/evidence do you remember, and was itbacktest/live/CI?
4. What would you click next to evaluate orcontactthem?
5. What do you understand about their personalcontribution and AIassistance?

Record actualresponses, viewport, route, visiblefirst screen, hesitation and misunderstoodclaims. Proposed acceptance: at least3of5, or2of3ifonly3available, identify targetrole/project purpose/proof scope/next action without beingprompted. Revise contenthierarchy for observedfailures and retestfreshreaderswherepossible. This is a small qualitative usabilitycheck and doesnotpredict hiringoutcomes. **Currentstatus: pending; no reader feedback was fabricated.**

## I. Copy-paste implementation assignment

```text
Implement the prioritized work in forecast-arena-audit-and-implementation-plan-2026-11-16.md.

First read current AGENTS.md/SPEC/TASKS/DECISIONS and preserve existing work. The audit
inspected source b072b2d22fa7c6f0af64e1c8d6df80cd70f97baa and ledger 9581949; refresh
current evidence before changing code. Do not redo already completed daily ML wiring:
16Nov published 33/33 ML forecasts; LangGraph 4 successes + 29 intentional sampling skips.
The reported evening-price question has ML 19.2%; Graph sampled the power-mean question.

Start with R01 finite numeric/schema/JSON validation and R02 actual read-only SQL.
Then implement shared forecaster participation/eligibility states R03, truthful numerical
model explanations and graph-sampling links R04, all-domain model/profile views R05,
and promotion labels R06. Preserve registered score populations and headline groups;
unresolved models get pending states, never made-up scores. Supplemental pairwise
comparisons must state their separate shared-question population and sample limits.

In parallel, address final-workflow incident monitoring, dependency triage and scheduling
preparation R07–R09. Clean CLI/docs/status R10/R11. Build the recruiter-first website,
README and GitHub metadata package R12–R15 using approved candidate facts and shared
proof data. Keep AI-assistance disclosure; do not infer personal mastery from generated
code. Add R16/R17 evaluation improvements after essential correctness and presentation.
Defer unrelated migrations/new services/models unless a concrete separately approved gap
justifies them. Coordinate shared schema/build/CSS/README/workflow files as section F.

Never rewrite/backdate sealed ledger records, manufacture historical skips/traces or
weaken checks/evaluation rules to improve appearance. Existing ML hashes/time/version
can be displayed; absent original numeric diagnostics must be labelled unavailable.
Future optional diagnostic artifacts must be versioned and recorded before lock.
Use fixtures/FakeLLM/disposable ledgers locally; no paid calls or large downloads merely
for coverage. Settings, credentials, personal facts and owner-gated items require the
appropriate actual authorization; prepare concrete reviewable packages first.

Run targeted regressions then appropriate full checks, fresh-process minimal-runtime
model loading, generated README/schema checks, all-page links, responsive/keyboard/
no-JS/print/a11y checks. Follow exact-SHA CI/stable/deploy/smoke evidence for an authorized
release. Verify actual ML scores only after natural source resolution; verify later
promotion/next batches without altering old records. Power batch 16 / target 17 first becomes
resolvable 16 Nov 12:30 UTC; other domains have different availability rules.

Deliver files changed, fixes linked to audit IDs, actual commands/results, source and
ledger SHAs/run links, observed public behavior, unresolved owner/future gates, and safe
rollback instructions. Mark a task complete only when its specific acceptance criteria
have evidence. Do not claim human testing, live operation or personal contributions
that were not actually verified.
```

