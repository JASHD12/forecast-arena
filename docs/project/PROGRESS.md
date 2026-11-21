# docs/project/PROGRESS.md - state between sessions

The agent keeps this file current. Newest information first. Keep it under 120 lines;
move older "Done log" lines to `docs/progress-archive.md`.

## Now

## Session summary (2026-11-19)

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

## In progress

Nothing. See the session summary above and `python scripts/status.py`.

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
