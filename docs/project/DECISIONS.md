# docs/project/DECISIONS.md - design decisions

One entry per decision a reviewer might question. Newest first.

Format:

```
## YYYY-MM-DD - Short title
Context: what forced a choice.
Decision: what was chosen.
Alternatives: what was rejected and why.
Made by: agent | human
```

## Decisions

## 2026-11-12 - Persistence needs 10 transitions, else it falls back to the base rate
Context: SPEC 8.2 says persistence is "estimated the same way" as the base rate, which
uses 0.5 below 10 instances, and falls back to the base rate when yesterday is unknown.
Decision: with fewer than 10 past days that followed the same outcome as yesterday,
persistence returns the base-rate probability (which itself is 0.5 below 10 instances).
The reason is in the forecast's `meta.fallback`.
Alternatives: 0.5 directly (throws away the base rate for no gain).
Made by: agent

## 2026-11-12 - Baseline history is an injected interface
Context: SPEC 8.1 asks for history replayed through the real question and resolver code
before the live record is long enough.
Decision: baselines read a `History`. `LedgerHistory` reads live resolutions written at or
before `asof`; `StaticHistory` holds replayed instances. Each domain's replay producer is
built with that domain (T024 onward) and uses the domain's own `generate_questions` and
`resolve`.
Made by: agent

## 2026-11-12 - Run manifests are filed by the UTC start date of the run
Context: SPEC 6 names `runs/YYYY/MM/DD-<job>-<n>.json` without saying which date.
Decision: the UTC date the run started. Day X is sealed by the first resolve run of X+1,
which starts after every run of day X has finished (shared concurrency group), so a
manifest never lands in an already sealed day. `batch_date` is still recorded inside.
Alternatives: batch date (a late resolve run for an old batch would write into a sealed day).
Made by: agent

## 2026-11-12 - Exact hash-chain formula
Context: SPEC 6 gives `sha256(prev_chain_sha256 + sorted "path:sha256" lines)`.
Decision: `sha256(prev + "\n" + "\n".join(sorted lines) + "\n")`, UTF-8; genesis prev is
64 zeros; days without files are sealed too so the chain has no gaps. Stated in
`arena/ledger/seal.py` and in METHODS.
Made by: agent

## 2026-11-12 - Lock file format
Context: AGENTS.md 6 asks for dependencies pinned by a lock file. The first session ran in a
cloud sandbox where PyPI was not reachable, so `uv lock` could not resolve.
Decision: `requirements/lock.txt` with exact `==` pins of the packages already installed in
that sandbox. `make setup` installs from it with uv (if present) or pip.
Alternatives: `uv.lock` (preferred long term; regenerate once network is available and
switch `make setup` to `uv sync`); no lock (rejected: breaks reproducibility).
Made by: agent

## 2026-11-12 - Runtime dependencies: pydantic and click
Context: SPEC 5 requires pydantic v2 models; SPEC/T015 needs a CLI with command groups.
Decision: `pydantic` for schemas, `click` for the CLI. Dev: `pytest`, `ruff`.
Alternatives: `argparse` (no nested groups without boilerplate), `typer` (adds a layer on
top of click for little gain).
Made by: agent

## 2026-11-12 - Time series without pandas
Context: T021 asks for "a tidy UTC-indexed frame". The series are small (hourly, at most
~70k points for the full SMARD history).
Decision: plain frozen dataclasses (`Point(start, value)`) sorted by UTC start, plus helper
functions for Berlin days. No new dependency.
Alternatives: pandas (heavy dependency for little gain at this size; may be reconsidered for
the ML tasks, with its own DECISIONS entry).
Made by: agent

## 2026-11-12 - Power templates: interpretation of SPEC 7.1
Context: SPEC 7.1 leaves rounding, percentile method, the evening block and window end open.
Decision: thresholds rounded half-up to whole EUR/MWh; daily statistics rounded half-up to
two decimals (SMARD precision) before strict comparison; percentiles by linear interpolation
(type 7); `evening_gt` = mean of the hours starting 17, 18, 19 Berlin; windows end at the
latest complete day available at the creation time (normally B); a template is skipped
(and logged) if its window has under 90% of its days or data is older than B-2; entity
`DE_LU` (the id pattern forbids hyphens). Degeneracy frequency = share of window days whose
statistic meets the threshold (for `up_vs_today`, share of day-on-day rises over 60 days).
Resolution reads every fetched value (they exist), not the conservative availability stamps.
Alternatives: thresholds to 0.1 EUR/MWh (false precision); nearest-rank percentiles.
Made by: agent

## 2026-11-12 - Daily job details
Context: SPEC 4/6/12 leave some job mechanics open.
Decision: the morning job refuses a batch date other than today's UTC date; it seals the
batch on its first successful run before lock (later runs that day are no-ops, so a failed
forecaster is not retried: its `error` skip stands); questions and forecasts are each
appended in one atomic write after re-checking the lock; a dry run works on a temporary
copy of the ledger. The resolve job checks first resolutions for source revisions for 7
days and records one `source_revised` void per question. Baseline history before the live
record is long enough comes from replaying the last 200 batch dates through the domain's
own generation and resolution code (`arena/forecasters/replay.py`).
Made by: agent

## 2026-11-12 - Clipping and the "perfect = 0" property
Context: SPEC 10 clips probabilities to [0.01, 0.99] for scoring; T028 asks that a perfect
forecaster scores 0. With clipping a perfect forecaster scores 0.0001.
Decision: every published score uses clipped probabilities (SPEC 10 wins: it is the scoring
rule). `brier(..., clipped=False)` exposes the bare rule, and the property test checks
perfect = 0 there and 0.0001 with clipping; constant 0.5 scores 0.25 either way.
Made by: agent

## 2026-11-12 - Site templates: Jinja2
Context: SPEC 11 names Jinja2 for the static site.
Decision: add `jinja2` (and its dependency `markupsafe`), pinned in the lock file, with
autoescaping on. No JavaScript, no external assets, no trackers, no cookies.
Made by: agent

## 2026-11-12 - Weather: Bright Sky (DWD) for both forecasts and observations
Context: SPEC 7.2 suggests Open-Meteo for forecast inputs and DWD observations (via Bright
Sky or the DWD files) for resolution.
Decision: use Bright Sky for both: observations (`historical`/`current` sources) resolve
questions; DWD MOSMIX (`forecast` sources) are the forecast inputs, snapshotted every
morning. Values filled in from another station count as missing. Daily statistics use the
hour-ending records of the Berlin day (01:00 ... 24:00 local; 23/24/25 hours).
Why: Open-Meteo's free tier is rate-limited per IP; from this sandbox's shared IP the daily
quota was already exhausted, and GitHub-hosted runners also share IPs, so the live job
could fail unpredictably. MOSMIX is DWD's official station forecast, CC BY 4.0, with the
same station ids as the observations. One source, one licence, one client.
Alternatives: Open-Meteo (above); reading DWD files directly (more parsing, same data).
Made by: agent

## 2026-11-12 - Weather templates: interpretation of SPEC 7.2
Context: SPEC 7.2 leaves the daily statistic, rounding and data volumes open.
Decision: daily maximum = highest hour-ending hourly temperature reading (DWD publishes
hourly instantaneous values through Bright Sky, not the 10-minute daily extreme);
precipitation = sum of hourly totals; both rounded half-up to 0.1 before comparing;
`tmax_gt` threshold = median of the last 14 complete observed days, rounded half-up to 0.5;
a day with more than 2 missing hours is left out of windows and voids a question at the
end of grace. Morning runs load 300 days of observations per station (one ~3 MB request
each, needed to replay ~200 batches for the baselines); resolve runs load 10 days.
Alternatives: DWD daily climate files (true daily extremes, but published with longer lag).
Made by: agent

## 2026-11-12 - Attention threshold and selection details (SPEC 7.3)
Context: K needs the median ratio views(t+3)/views(t) of top-200 articles over 90 days.
Fetching per-article series for 200 articles x 90 days would cost ~18,000 requests.
Decision: compute the ratios from the daily top lists only (two cached lists per day). An
article absent from the t+3 list gets that list's lowest view count (an upper bound, so the
median ratio is slightly overestimated; stated in the module docstring). R = the latest
day whose pageviews count as available (X+2 00:00 UTC rule) and whose list exists,
normally B-2. K is rounded to two significant figures. Articles are identified by
`<wiki>.<percent-encoded title>` (hyphens encoded, since ids use hyphens as separators).
The blocklist (`src/arena/domains/attention_blocklist.txt`) excludes adult content, death
and violence, war, disasters and similar, erring on exclusion. Attention is not replayed
for the baselines: base rates are per article, so `base_rate` answers 0.5 (fewer than 10
instances) as SPEC 8.1 prescribes.
Made by: agent

## 2026-11-12 - Markets templates (SPEC 7.4)
Decision: log returns between consecutive published fixings (four decimals), rounded to 6
decimals; `absmove_gt` threshold = median absolute return of the last 60 returns, rounded
half-up to 0.0001, compared strictly; `up` is YES only if F1 > F0 (equal is NO). Target
date = day of F1 (next publication day). Questions only on publication days. Multi-day gaps
(Friday to Monday, holidays) are not rescaled in the threshold: the question is stated in
terms of the next fixing, whatever the gap.
Made by: agent

## 2026-11-12 - ML dependency: scikit-learn (with numpy, scipy)
Context: SPEC 8.3 asks for gradient-boosted quantile regression with calibration.
Decision: scikit-learn's `HistGradientBoostingRegressor(loss="quantile")` (available since
1.1; checked in the installed 1.9.1 docstring) and `LogisticRegression` for Platt-style
calibration. Pulls in numpy, scipy, joblib, threadpoolctl, narwhals, cloudpickle (all
pinned). `make` sets `OMP_NUM_THREADS=1` for tests: two OpenMP processes on four cores
slowed the suite from 20 seconds to over 15 minutes, and one thread keeps fits deterministic.
Alternatives: LightGBM (extra native dependency, no clear gain at ~3,000 rows).
Made by: agent

## 2026-11-12 - LLM adapters: official Anthropic SDK; raw HTTP for OpenAI-compatible
Context: SPEC 9.1 asks for an Anthropic adapter and an OpenAI-compatible adapter.
Decision: the Anthropic adapter uses the official `anthropic` Python SDK (2.x; pinned with
its dependencies, including `httpx2`); its base URL is pinned so that an ambient
`ANTHROPIC_BASE_URL` cannot redirect it (configuration comes only from `ARENA_*`). The
OpenAI-compatible adapter is a small stdlib HTTP client so it works with any provider or
local server. No sampling parameters are sent to Anthropic (current models reject them);
the forecast records "provider default". Server-side refusal fallbacks are not enabled: a
refusal becomes an `error` skip, so every forecast is attributable to exactly one model.
Alternatives: raw HTTP for Anthropic too (rejected: the SDK is the documented client);
enabling fallbacks (rejected: would mix models under one forecaster version).
Made by: agent

## 2026-11-12 - Note on this file
Context: a scripted edit on 2026-11-12 dropped the "Proposals" heading, so the entries
above (written during T027-T060) were silently not saved; they were restored the same day
from the session record. Edits to this file now assert that their anchor exists.
Made by: agent

## 2026-11-12 - Agent news backend: GDELT DOC API (RSS output)
Context: SPEC 9.3 names GDELT or outlet RSS feeds as candidates for `search_news`.
Decision: GDELT DOC 2.0 in ArtList mode with RSS output, bounded by `enddatetime` = the
forecast time, so the agent only sees items published before it (no leakage). GDELT's
terms allow any use with a citation and link (shown in tool output). RSS output is used
because the documentation lists the RSS format but not the JSON field names. Requests are
spaced 5 seconds apart as GDELT asks. Only title, outlet (link host), URL and time are
kept. Risk: GDELT throttles shared IPs (seen here); a failed search is a tool error the
agent sees, never a reason to guess.
Alternatives: individual outlet RSS feeds (terms differ per outlet; no time filter).
Made by: agent

## 2026-11-12 - Model artefacts on the ledger: promoted models only, xz-compressed
Context: SPEC 6 puts model artefacts under `models/` on the ledger; SPEC 15 says keep the
ledger small. A power model is ~10 MB raw, ~4 MB with default compression, ~1.3 MB with xz.
Decision: store xz-compressed joblib artefacts, with metadata (artefact SHA-256, training
cut-off, code SHA, package versions), and only for models that the weekly job promotes;
promotions are new files (`models/<domain>/promotions/`), never overwrites. `ledger
verify` treats `models/` and `meta/` as non-record files (only `runs/` and `chain/` hold
single-record JSON). Loading checks the artefact hash.
Made by: agent

## 2026-11-12 - Weather model stage 1: fixed rules on the MOSMIX forecast
Context: SPEC 8.3 asks for rule-based weather probabilities until 60 days of as-of forecast
snapshots exist.
Decision: `tmax_gt` uses a normal distribution around the forecast daily maximum with a
2.0 C standard deviation; `wet_day` uses a fixed step function of the forecast daily total
(module docstring). Both were set before any live resolution and are labelled
`weather-rules-r1`. A missing forecast is an `error` skip.
Alternatives: calibrating the spread on observations vs. forecasts (impossible without
as-of forecast history; that is stage 2).
Made by: agent

## 2026-11-12 - Markets direction fixed at 0.5; persistence falls back for markets
Context: SPEC 8.3 fixes direction at 0.5 unless a backtest shows skill.
Decision: no direction model was built, so `up` is 0.5 (H3 stays a clean null test). The
volatility model (`absmove_gt`) is shipped although its backtest gain over `base_rate`
(-0.0013 Brier, interval [-0.0050, +0.0024], 2024-11 to 2026-10) is not supported; the
model card says so. `persistence` equals `base_rate` on markets because yesterday's
outcome (the previous day's fixing) is published at 16:00 CET, after the 09:30 UTC lock,
so it is never known at forecast time; the fallback is the rule of SPEC 8.2.
Made by: agent

## 2026-11-12 - Common set uses the active members of the comparison group
Context: SPEC 10's common set is "questions answered by every forecaster in the comparison
group". Before `ml` or the LLM forecasters are enabled, a strict reading gives an empty
headline board.
Decision: the common set is the intersection over the group members that have at least
one scored forecast in the board's scope; the board lists which forecasters it covers.
The 300-forecast threshold counts questions x covered forecasters. Without an official
start date, headline boards are empty and labelled "too early to tell".
Made by: agent

## 2026-11-12 - Accessibility lint: axe-core in Chromium (tools/a11y)
Decision: `make a11y` builds the site from the offline e2e run, link-checks it and runs
axe-core 4.14.0 on every top-level page and a sample of question pages, at 1200 px (light)
and 390 px (dark); serious or critical violations fail the job. Node dependencies are pinned
in `tools/a11y/package-lock.json`; CI installs them and Chromium in a separate job.
Alternatives: pa11y (wraps the same engine, more dependencies); a hand-written linter.
Made by: agent

## 2026-11-12 - Weekly job: promotion rule, MLflow on a SQLite file, public summaries
Context: SPEC 12 asks to promote a model only if it is not worse than the current one on
the most recent 28 days by a documented rule, and to log runs with MLflow (file-backed).
Decision: the rule is in `src/arena/ops/weekly.py`: a candidate trained before the 28-day
window (ending 3 days ago) is scored on that window's real questions next to the current
model; if not worse, the same recipe is refitted with the latest outcomes and promoted
(the current model may have seen part of the window, which favours keeping it). MLflow
3.18's plain file store is in maintenance mode and refuses to start without an opt-out,
so runs are logged to a SQLite file (`mlruns/mlflow.db`, still file-backed, no server).
The database is mutable and therefore not on the append-only ledger; each run's JSON
summary is written to `models/weekly/` on the ledger instead. MLflow (`mlflow-skinny`
with SQLAlchemy and Alembic) is pinned in `requirements/tracking.txt`, installed by the
weekly workflow and CI, not by `make setup`.
Made by: agent

## 2026-11-12 - No remote MLflow tracking server (T082)
Context: T082 asks whether a remote tracking server is worth a human item.
Decision: no. Each weekly run logs to a local SQLite file and publishes a JSON summary
to the ledger; the Experiments page (linked from Status) lists every summary. A server
would add an always-on service, credentials and cost (against SPEC 2.6) for information
the ledger already holds publicly. Revisit only if experiments grow beyond weekly runs.
Made by: agent

## 2026-11-12 - Drift report with Evidently, metrics on the ledger, HTML as an artifact
Context: SPEC 12 asks for a weekly Evidently drift report published on the site.
Decision: Evidently 0.7.23 (pinned with pandas 2.3.3 in `requirements/tracking.txt`; it
does not import with pandas 3) compares the power features and the model's median
prediction on the 28-day window with the year before. Its telemetry dependency is
disabled with `DO_NOT_TRACK` in code and in the workflow. The full HTML report is ~4 MB
of JavaScript, so it is kept as a 90-day workflow artifact; the computed metrics are
written to the weekly summary on the ledger and shown on the Experiments page (no
JavaScript on the site). Performance over time is the weekly Brier series in the
summaries.
Made by: agent

## 2026-11-12 · LLM forecasters run from the first real morning run

- Context: `build_forecasters` has always included `llm_plain`, `llm_context` and `agent`,
  recording `model_missing` skips while no key was set. With H04 done, the first real
  morning run (rehearsal, 2026-11-13) will make real calls, before T046/T065 are ticked.
- Decision: keep it. The calls run only in Actions, under the SPEC 9.4 caps (100
  requests, 400k tokens per UTC day), forecasts are written before lock like every other
  forecaster, and the rehearsal period is not part of the official record. T065 and T068
  are still ticked only after their own checks.
- Alternative: hide the LLM forecasters until T065 (rejected: no integrity gain, and the
  rehearsal is exactly where cost and failure modes should show up).

## 2026-11-12 · More interesting weather questions (owner approved ideas 1, 3, 4)

- Context: the owner asked for questions people would enjoy voting on and approved, from
  the proposal below, (1) plain-language titles, (3) city duels and (4) event-style
  weather questions.
- Decision:
  - (1) `arena.site.titles.plain_title` builds a short headline from template and
    parameters at site-build time. Display only: not stored in the ledger, not shown to
    forecasters; the exact text and rule stay on every question page. Titles always name
    the date (never "tomorrow", which would be wrong on archived pages).
  - (3) `warmer_than` and `wetter_than` for two fixed duels, Berlin vs Munich and Hamburg
    vs Frankfurt (fixed pairs keep the daily count small and the series comparable).
    Strictly greater; ties are NO. Two dry days are therefore NO.
  - (4) `frost_day` (DWD "Frosttag", daily minimum below 0.0 C) and `gust_gt` (adaptive
    threshold like `tmax_gt`; Bright Sky `wind_gust_speed`, km/h, maximum of the previous
    hour, verified in the OpenAPI document 2026-11-12). Berlin-Dahlem reports no gusts, so
    it has no gust question. The degeneracy rule (SPEC 7.0) skips a template when it is
    almost always YES or NO, so frost questions appear only in the cold season.
  - Not built: snow (no hourly snow observation at these stations through Bright Sky; the
    `condition` field is derived, not measured) and "tropical night" (a full-day minimum
    >= 20 C is so rare in Germany that it would always be skipped; DWD's own definition
    uses an 18-06 UTC window, which would need its own day boundary).
  - The v1 templates are byte-for-byte unchanged (frozen goldens
    `tests/fixtures/golden/weather/*_v1_frozen.jsonl`), and so is their forecaster
    context. The new templates get a richer context (minimum temperature, gusts, both
    cities).
  - `ml` for weather becomes `weather-rules-r2`: the r1 rules are unchanged, and fixed
    rules are added for the new templates before any of them resolved (I8). Documented in
    `src/arena/forecasters/ml_weather.py`.
  - Weather can now produce up to 19 questions a day (8 + 4 frost + 3 gust + 4 duels),
    so a full day is above SPEC 1's "about 25". The LLM sample per domain is unchanged (3),
    so LLM cost does not grow.
- Alternatives: all six city pairs (rejected: 12 duel questions a day, mostly
  redundant); a fixed storm threshold for gusts (rejected: almost always NO, so skipped as
  degenerate).

## 2026-11-12 · Site redesign (owner request: "looks very basic")

- Decision: new stylesheet and home page: a hero with the research question and the key
  numbers, question cards with one labelled bar per forecaster (the percentage is always
  printed, so nothing depends on colour), friendly forecaster and domain names (ids kept
  in tables and data), rounded cards and tables, light and dark themes.
- Still SPEC 11: static, no JavaScript, no cookies or trackers. No web fonts: loading
  Google Fonts would send every visitor's IP address to Google, which German courts have
  treated as a GDPR violation (LG München I, 2022); the system font stack avoids that.
- Checked with `make a11y` (axe-core, desktop light and phone dark): 0 serious/critical.

## 2026-11-12 · Crypto domain (owner request)

- Context: the owner asked for Bitcoin and other major coins and will create a CoinGecko
  account.
- Decision: a `crypto` domain with five fixed coins (Bitcoin, Ethereum, Solana, XRP, BNB)
  and two templates per coin, `up` and `bigmove`, about the UTC day D = B+1, built like
  the ECB markets domain (same threshold and degeneracy rules, same EWMA + Student-t `ml`
  rule as `crypto-ewma-t5-r1`, direction 0.5). Prices are CoinGecko's daily 00:00 UTC
  points, known from 01:00 UTC (docs: after 00:35). Resolution after D+1 01:00 UTC with
  revisions recorded (CoinGecko may revise for 2 days), the SMARD approach, rather than
  waiting 2 days.
- The Demo key travels only in a request header, never in a URL, log or the ledger.
  Without a key the domain is skipped with a warning (the keyless API is documented as
  unsuitable for scheduled use).
- Not live yet: the API terms page could not be read by the agent (see SOURCES.md), the
  key is the owner's, and passing a new secret to a workflow is not a standing approval.
  All three are in HUMAN_TODO H12; T045e waits for it.
- Alternatives: hourly prices for "close of the European day" questions (rejected: Demo
  hourly history is 100 days, too short for degeneracy windows); "above a round price"
  questions (rejected for now: the threshold choice would be arbitrary; `bigmove` plus the
  plain title already reads naturally).

## 2026-11-12 · Site improvements and EU compliance (owner request)

- Context: the owner asked to "follow all rules" (EU) and to make the site better
  "visually, functionally in all things".
- Decision (site): Guide & FAQ page; Imprint and Privacy pages linked from every page;
  question pages with a YES/NO verdict, "who was closest" (per-question Brier, display
  only), AI labels and collapsible raw forecasts; archive grouped by day with topic
  filters (static pages `questions/topic-<domain>.html`, no JavaScript); leaderboard with
  friendly names and score bars against the 0.25 coin-flip line, rehearsal scores first
  until the official start; "how it works" strip on Home; Atom feed `feed.xml` (last 7
  batches); favicon, share metadata; a 404 page; print styles.
- Decision (rules): `docs/COMPLIANCE.md` lists each rule, its status and the owner's part.
  Built: no scripts, cookies or third-party requests (tested), referrer off, an AI
  disclosure on every page, CC BY change notes in the credits. Not built (owner): the
  Imprint and Privacy text (H05).
- The per-question score is display only; leaderboards still come only from
  `arena.scoring` (SPEC 10 unchanged).

## 2026-11-12 · Frontier-model option and a tech-stack page (owner request)

- Context: the owner wants "advanced models" and a site that shows the stack to hiring
  managers.
- Decision: `ARENA_LLM_EFFORT` (Anthropic `output_config.effort`, unset = provider
  default) and the workflow variables `ARENA_LLM_MAX_OUTPUT_TOKENS` and
  `ARENA_LLM_MAX_TOKENS_PER_DAY` (defaults 400 and 400000 = SPEC 9.4). Current Claude
  models always think, and thinking tokens count against `max_tokens`; a larger model
  with the 400-token cap could stop before its answer, so the switch is documented with
  matching settings (HUMAN_TODO H13). The effort is recorded on every forecast.
- Server-side refusal fallbacks stay off (see the Anthropic adapter): a forecast must be
  attributable to exactly one model; a refusal is a recorded skip.
- A model switch is a version change visible on the site; it is not made because of how a
  live question resolved (I8).
- `stack.html` describes only what exists; library versions are read from the build
  environment and the live models from the ledger, so the page cannot overstate.

## 2026-11-12 · Cost ceiling: Haiku 5.5, about $1 a month at most (owner decision)

- Context: the owner does not want the project to cost money; asked, they chose to keep
  Claude Haiku 5.5 with tighter caps rather than switch the AI forecasters off.
- Decision: the workflows default `ARENA_LLM_MAX_TOKENS_PER_DAY` to 150000 (SPEC 9.4's
  400000 stays the code default and can be restored with the Actions variable). With 100
  requests x 400 output tokens and Haiku 5.5's prices ($0.10 / $0.50 per million), the
  worst case is about $0.03 a day. When the cap is reached, remaining LLM forecasts are
  `budget_exhausted` skips (I6), shown on the Status page. Frontier models (H13) and the
  model-size comparison proposal are withdrawn. Everything else stays free: public-repo
  GitHub Actions and Pages, free data sources, CoinGecko's free Demo plan.

## 2026-11-12 · Data-science additions (owner request: skills asked for in AI/ML/DS jobs)

- Context: the owner asked for an advanced, commonly requested stack at no extra cost.
  Only working features were added; nothing is listed on the site that is not used (I5).
- Decision:
  - DuckDB SQL over the ledger at every site build, with the queries and results shown on
    `data.html`, and the ledger tables published as zstd Parquet (`data/*.parquet`).
    New dependency `duckdb` (runtime): one wheel, no server.
  - Diebold-Mariano test (Newey-West long-run variance on daily-averaged loss
    differences, HLN correction, Student t) in backtest reports next to the day-block
    bootstrap. Supplementary only: SPEC 10 headline rules are unchanged.
  - Permutation feature importance for the promoted power model in the weekly job,
    stored in the weekly summary and shown on Experiments. Never blocks the job.
  - mypy in `make check` (and CI); 19 findings fixed with correct types, not ignores.
    New dev dependency `mypy`.
- Alternatives rejected: PyTorch/deep learning (a large install with no expected gain on
  these small tabular problems; would be listed without honest use), a paid dashboard
  host or vector database (cost), SHAP (heavier dependency; permutation importance is
  model-agnostic and enough here).

## 2026-11-12 · Legal text drafts (owner request)

- Context: AGENTS.md says the agent must not invent legal text; the owner then asked the
  agent to write the Imprint and Privacy text.
- Decision: drafts in `docs/legal/` that state only facts about this site (no cookies,
  no trackers, GitHub Pages IP logging, GDPR rights) and leave every personal detail as a
  `[FILL IN: ...]` placeholder. The site never publishes a file containing a placeholder
  (tested). The owner checks and completes them; they are not legal advice.

## 2026-11-12 · Quantile diagnostics and site round 4 (owner request)

- The weekly job also scores the promoted power model's full predictive distribution on
  the evaluation window: mean pinball loss over the 13 quantile levels and the empirical
  coverage of the central 80% and 90% intervals, after sorting the predicted quantiles
  (rearrangement) so they never cross. Published in the weekly summary and on
  Experiments. Display and monitoring only; question probabilities are unchanged.
- Site: leaderboard podium and a forest plot of Brier scores with their 95% day-block
  intervals (the same numbers as the tables), an HTML/CSS architecture diagram, and an
  About page with the owner's name and city (given by the owner for the Imprint).
- The ensemble (T090) is not built yet: it depends on T057 (ml live), and AGENTS.md says
  never to skip ahead of unmet dependencies.

## 2026-11-13 · Portfolio roadmap (owner approved)

- Context: the owner wants the project to win AI/ML/DS working-student interviews in
  Germany and approved `docs/ROADMAP.md` (Phase 10 in docs/project/TASKS.md).
- Decisions (owner): self-hosted JavaScript is allowed on the site (no cookies, no
  storage, no third-party requests, pages work without it); add measured ML challengers
  (LightGBM + Optuna + SHAP, a PyTorch network, statistical and foundation-model
  benchmarks, conformal intervals), LLM engineering (RAG tool, LangGraph agent, a local
  open-source LLM, tracing, an eval harness, an MCP server), recruiter, German and
  dashboard pages, engineering breadth (FastAPI, Docker, kind, dbt, an Airflow DAG mirror)
  and a public players' leaderboard with questions published the evening before.
- This supersedes the 2026-11-12 entries that rejected JavaScript, PyTorch and SHAP.
- Constraints that stay: zero extra cost (Haiku 5.5 under 150k tokens/day; everything
  else free), I1-I8, and I5 applied strictly: nothing is named on the site that CI does
  not run, and every challenger's measured result is published even when it loses.
- The official record starts only after these changes are live (T110), so it is not
  disturbed by version churn.

## 2026-11-13 · LightGBM + Optuna + SHAP challenger (T112)

- The power `ml` forecaster gets a second candidate family in the weekly job:
  LightGBM quantile regressors (`power-lgbq`) with hyperparameters tuned by Optuna (TPE,
  seed 0, 20 trials, two time-series folds with a 7-day gap, mean pinball loss at
  0.1/0.5/0.9). Features, calibration and question logic are the champion's, so only the
  learner differs. It is promoted only if it is not worse than the champion on the same
  recent questions (T111). SHAP (TreeExplainer) explains it when it is the champion.
- New optional dependencies in `requirements/ml.txt` (lightgbm, optuna, shap), compiled
  with `requirements/lock.txt` and `requirements/tracking.txt` as constraints (pandas
  stays 2.3.3 for Evidently). Installed by CI, the weekly and the deps workflows; tests
  skip without them, so `make setup` alone still works.

## 2026-11-13 · Health checks and incident issue (T033)

- `arena health check` implements the five SPEC 12 checks; "sources fresh" is measured by
  each domain's latest question time (96 h for markets, which publishes on working days);
  "overdue" means unresolved more than 5 days after `resolve_after` (longer than every
  domain's grace period). The parse-failure rate is only judged from 5 LLM answers on.
- One issue, deduplicated by its fixed title; the workflow token opens, comments on and
  closes it via `gh` (standing approval 5). The weekly workflow checks only real runs (a
  dry run has no ledger checkout). Pages still deploys when a check fails. A dispatch
  input `fail_health` adds a failing check for testing the alert path.

## 2026-11-13 · Test quality (T118)

- Hypothesis property tests and pytest-cov (dev dependencies only). The first property run
  found that `ledger verify` crashed on a file with invalid UTF-8; such a file is now a
  `LedgerError`, so verify reports it as a failure.
- "Schema checks on source responses" already exist as strict parsers that raise on any
  missing or malformed field (`parse_top`, `parse_weather`, `parse_daily`, the SMARD and
  ECB parsers, each with tests); pandera was not added, to avoid a second validation layer.

## 2026-11-13 · Official start: clean days and the not-before gate (T035, T110)

- A clean day: a real morning run succeeded, no real run failed, at least one health
  report was recorded and all passed (a failed report is what opens the incident issue,
  so this is the ledger-side record of "no open incident"), and the day is sealed. Health
  reports are written to `health/YYYY/MM/DD-<job>-<n>.json` and sealed with their day,
  so the streak is auditable from the public ledger alone.
- The official start is the day after the first 5 consecutive clean days, but never
  before `ARENA_OFFICIAL_START_NOT_BEFORE`. The workflows default that to 2099-12-31 until
  the roadmap's model and timing changes are live (owner decision); the agent then sets
  the real date in the workflow files. `meta/official_start.json` is written once, when
  the start takes effect; `Ledger.write_raw` refuses any second write.
- Only completed days count (up to yesterday); the decision runs after every real job.

## 2026-11-13 · Time-series benchmarks for power (T114)

- New optional file `requirements/ts.txt` (statsmodels 0.15.0, chronos-forecasting 2.3.2
  and their dependencies, including transformers), compiled with the lock, tracking, ML
  and torch files as constraints, and installed by CI.
- ETS, SARIMAX and Chronos-Bolt tiny are *local* benchmarks: each question is answered
  from the same 28-day as-of context the live forecasters see, with no training on other
  days and no calibration. They appear in the backtest table and model card only; they
  are not live forecasters and not promotion candidates (adding them live would need a
  SPEC 8 change).
- Chronos weights are pinned to a revision. The Hub download uses plain HTTPS
  (`HF_HUB_DISABLE_XET=1`), so only huggingface.co and us.aws.cdn.hf.co are needed.
  CI tests use a fake pipeline and never download weights.
- Alternatives: AutoGluon (far heavier); Chronos-2 or larger Bolt sizes (slower on CPU,
  no need for a benchmark); statsforecast (one more library for the same models).

## 2026-11-13 · RAG tool: similar past questions (T120)

- The agent gets one more read-only tool, `similar_past_questions(k, same_domain)`, with
  prompt version v2 for the agent only (`agent_system_v2` adds one paragraph; the other
  v2 files are copies of v1). llm_plain and llm_context keep v1. The forecaster version
  shows `prompt-v2` and `rag-<embedder>`, so the change is visible on the site.
- Embeddings: fastembed with BAAI/bge-small-en-v1.5 (ONNX, CPU, no API cost), cached in
  `data_cache/fastembed`. The index is rebuilt in memory at each morning run from the
  ledger (a few thousand short texts embed in seconds), so there is no separate index
  file that could drift from the ledger. The roadmap's Parquet/DuckDB index file was
  therefore not needed.
- Leakage rule (I3): only questions whose first resolution was recorded strictly before
  the forecast time, and that are not voided out of scoring, can be returned; open
  questions are never indexed; the question itself is excluded. Covered by a test.
- Switched on in the morning workflow (`ARENA_AGENT_RAG`, default 1). If fastembed is
  missing while it is on, the run fails instead of silently dropping the tool (I6).
- This is before the official start (T110 gate), so the record starts with v2.

## 2026-11-13 · LangGraph agent `agent_graph` (T121)

- A LangGraph `StateGraph` (plan -> retrieve -> research <-> tools -> critique, then
  parse with one repair) over the project's own `LLMClient`. Deviation from the roadmap
  text ("through langchain-anthropic"): a LangChain chat model would call the provider
  itself, outside `GuardedLLM`/`BudgetGuard`, and would need its own handling of thinking
  blocks. Keeping our client makes the daily caps hold by construction, keeps FakeLLM
  tests, and saves a dependency. LangGraph does the orchestration only.
- Same tools, output contract, skips and trace format as `agent`. The retrieve node
  fetches the base rate and the similar past questions automatically (two calls on top
  of the model's own tool budget). One question per topic per day: `daily_sample` with
  n=1 is a subset of the agent's n=3 sample, so the two agents are compared on the same
  questions (framework agent vs hand-written loop, same model and tools).
- Not part of the headline common set (`COMMON_GROUP`, SPEC 10 unchanged): with one
  question a day it would shrink that set. It is on the all-questions boards and has a
  power-analysis pair against `agent`.
- `langsmith` arrives as a LangGraph dependency; it sends nothing unless LangSmith
  tracing is switched on with its own key, which is never set.
- On in the morning workflow (`ARENA_AGENT_GRAPH`, default 1); a missing langgraph fails
  the run (I6). Before the official start (T110 gate).

## 2026-11-13 · Local open-weights LLM `llm_local` (T122)

- Qwen2.5-1.5B-Instruct (Q4_K_M GGUF, Apache-2.0, not gated) through llama.cpp on the
  runner CPU; same prompts and contract as `llm_context` (subclass), same daily sample.
  Greedy decoding, fixed seed, output constrained by llama.cpp's JSON-schema grammar (the
  parser still validates). Deadline 120 s per call, 900 s per run; a timeout is an
  `error` skip. Token usage is approximate (tokenizer count of the message texts, and
  one output token per streamed chunk) and never counts against the API caps.
- Alternatives: Llama 3.2 1B (gated licence acceptance: an owner action, S2); Qwen3
  small models (thinking mode adds tokens); Ollama (a background server, S9).
- Operations: installed in the morning workflow only (CI uses a fake backend), with the
  pip wheel cache and a fixed-key cache for the weights in `models_cache/` (kept out of
  the per-run `data_cache` cache). If the build or the load fails, `llm_local` records
  `model_missing` skips that name the reason and the other forecasters run normally;
  the batch is never put at risk for an optional forecaster.
- Colour: the validated palette has 8 slots, all taken; `llm_local` shares slot 6 with
  the not yet active ensemble until T134 adds a validated ninth colour.

## 2026-11-13 · LLM tracing and the LLM observability page (T123)

- `TracingLLM` wraps every model client (outside `GuardedLLM`, so refused calls never
  reach it and the cap logic is unchanged) and records one OpenTelemetry-shaped span per
  call: forecaster, question, prompt version, model, tokens, latency, requested tools,
  repair flag, error. No prompt or answer text. Scope comes from a context variable set
  around each forecast in the morning job. Times come from the injected `Clock`, so runs
  stay reproducible in tests.
- Spans are written into the existing `agent_traces/YYYY/MM/DD.jsonl` (one line per
  forecaster and question; already sealed with the day), not a new ledger family.
- No OpenTelemetry SDK or collector: it would need a backend to send to (an account or
  a service). The span shape matches OTel names so it could be exported later.
- Cost on the site is an estimate from recorded tokens and a dated list price
  (`site/llm_obs.py`); unknown models show "no price" rather than a guess.

## 2026-11-13 · LLM evaluation harness (T124)

- Golden set `evals/golden/power-2026-10.jsonl` (186 power questions, batch days
  2026-10-01 to 2026-10-31): generated and resolved by the production domain code from
  SMARD history, each with the as-of context of that morning and the benchmark base rate
  from replayed history before it. Frozen: its SHA-256 is in every result. Honest limit,
  stated on the page: the answers were known when an eval runs, so training-data
  contamination cannot be ruled out (daily auction prices are an unlikely thing to
  memorise, but the live record is the real test).
- Variants: `llm_plain` vs `llm_context` (same model; prompt and information differ),
  optionally `llm_local`. The agent is not evaluated offline (its news and Wikipedia
  tools would read today's web, which would leak).
- CI gate: a FakeLLM run on the committed set inside `make check` (every answer parsed
  and scored, metrics computed). Real runs only by manual dispatch of `llm-eval.yml`,
  with the eval's own hard caps (default 60,000 tokens; about one US cent on Haiku 5.5),
  separate from the live daily cap. The workflow writes no ledger; its artifact is
  committed to `evals/results/` by the agent and shown on `evals.html` under an
  EVALUATION banner, never in a leaderboard (I4).

## 2026-11-13 · Output cap 1024 per call, found by the first eval (T124)

- Evidence (`llm-eval` runs 43418758614 and 43420219082 on the golden set, not the live
  record): with 400 output tokens per call, Claude Haiku 5.5 at effort low stopped with
  `max_tokens` on 10 of 12 first answers of `llm_plain` and 6 of 12 of `llm_context`;
  the repairs then used up the eval budget. Thinking tokens count against the cap.
- Decision: forecasters now take the per-call cap from `ARENA_LLM_MAX_OUTPUT_TOKENS`
  (before, a hard-coded 400 inside each forecaster also applied), the cap is part of
  every LLM forecaster's version (`|out-N`, visible in the changelog), and the workflow
  default is 1024. The SPEC 9.4 code default (400) and the daily cap (150,000 tokens)
  are unchanged; fewer repairs mean fewer calls, so daily use should not rise much.
- This is a format and cost fix from an evaluation, not a change made because of how a
  live question resolved (I8). It happens before the official start.

## 2026-11-13 · MCP server `arena mcp` (T125)

- Official `mcp` SDK 2.3.0 (`MCPServer`), stdio only (no network listener, no hosting).
  Four read-only tools over a snapshot of the ledger loaded at start; tools carry the
  read-only annotation. SQL: a single SELECT/WITH statement, at most 200 rows, DuckDB
  external access off and the configuration locked after loading (tested: `read_csv` of
  a local file fails, `SET` is refused).
- The leaderboard tool scores every resolved question, rehearsal included, and says so;
  the site's headline boards keep the official-record rule.
- Installed by CI (`requirements/mcp.txt`); tested in-process and over a real stdio
  subprocess with the SDK's own client.

## 2026-11-13 · The game and the first JavaScript (T130)

- One self-hosted `static/app.js` (vanilla, no dependencies) for `play.html` only, per the
  SPEC 11 amendment. The game data is embedded as a JSON data block (never executed),
  so the page works from `file://` and under `script-src 'self'`; `data/game.json` is
  also written for other consumers. Without JavaScript the page shows a static table of
  resolved questions and every forecast.
- Decks: live resolved questions with every forecaster's published probability; and a
  practice deck of 60 past days from the golden evaluation set against the base rate,
  labelled practice everywhere (not a record, not a score). Scores stay in memory.
- CSP meta on every page: `default-src 'self'; script-src 'self'; style-src 'self'
  'unsafe-inline'` (a few templates use inline style attributes for bar widths). The
  accessibility checker injects axe with Playwright's `bypassCSP`, a test-only setting.
- `make a11y` also plays one round per deck in Chromium, checks the no-JavaScript
  fallback and fails on any request that leaves the site.

## 2026-11-13 · Question page data chart (T131)

- The chart is drawn from the morning snapshot (`snapshots/<domain>/.../morning_context`),
  so it shows exactly the as-of data the forecasters had, plus the observed value once
  resolved. Server-side SVG with a title, a description and a data table (no script).
- Per domain: power (the asked daily statistic, threshold), weather (the asked variable;
  both cities for duels, no threshold line), attention (daily views, threshold), markets
  and crypto (the rate or price series only: those questions are about changes, so no
  level threshold or observed level is drawn, which would mislead).
- The trace panel (T123) and previous/next links within the same topic complete the page.
  The retrieved similar questions (T120) are not shown: the tool's results are not
  stored (only call metadata), and recomputing them at build time could differ from what
  the agent saw.

## 2026-11-13 · Leaderboard matrices and sortable tables (T134)

- Skill-by-topic heatmap and a head-to-head matrix (row minus column, paired Brier
  differences with day-block 95% intervals, coloured only when the interval excludes
  zero). Display only; the boards and their wording rules stay the verdict (SPEC 10).
  Cells with fewer than 10 questions stay gray and say "few" or "–".
- Colours: the diverging blue/red pair and neutral grays of the dataviz reference
  palette (light #f0efec, dark #383835), three steps per arm mixed from the neutral
  towards each pole; contrast checked with the palette validator's WCAG function: every
  step is at least 5:1 against its text colour (#10162a in light, #ffffff in dark). The
  sign and the number are printed in every cell, so colour is never the only cue.
- Sorting is progressive (buttons added by app.js, `aria-sort` set); without JavaScript
  the tables are complete, just unsorted. Checked in Chromium by `make a11y`.
- Not done here: the cost-vs-accuracy scatter for LLMs from the roadmap; the LLM page
  already shows cost per forecaster next to the scores (proposal for later).

## 2026-11-13 · Home and global polish (T137)

- `app.js` now loads on every page (deferred, self-hosted, CSP `script-src 'self'`) for:
  a countdown to the 09:30 UTC lock from the visitor's own clock, a search box on the
  question archive, and a theme toggle (auto/light/dark) kept in memory only, so it
  resets on every page load: remembering it would need storage, which the site does
  not use. Without JavaScript: a static lock sentence, no box, no toggle.
- The CSS dark tokens now apply under `prefers-color-scheme: dark` unless
  `data-theme="light"`, and always under `data-theme="dark"`.
- Sticky header; a 1200x630 `og:image` (`static/og.png`, rendered once from an HTML card
  with Playwright) with an absolute URL.

## 2026-11-13 · Methods, Guide, Data depth and the notebook (T138)

- Methods: a worked scoring example (made-up forecasts, real arithmetic) that shows one
  overconfident miss outweighing two good calls. Guide: a five-command verification
  walkthrough. Data: a data dictionary generated from `analytics/sql.py` (a test fails
  if a column is undocumented).
- `notebooks/explore.ipynb` uses pandas and DuckDB on the open Parquet files. It is
  committed without outputs and executed in CI (`make notebook`, nbclient) on the offline
  e2e export, which is fixture data, so no fixture result is ever committed or published.
  Polars from the roadmap was left out: it is not a project dependency and nothing is
  listed that the code does not use. New pins in `requirements/nb.txt`.

## 2026-11-13 · Streamlit dashboard (T143)

- `apps/dashboard/streamlit_app.py`: topic and forecaster filters, Brier by forecaster, a
  running-average chart, a calibration table and skips, computed with DuckDB and pandas
  from the four open Parquet files. It reads `ARENA_DATA_DIR` (local) or
  `ARENA_DATA_URL` (default: the published site's data folder), so it needs no secret.
- Tested in CI with Streamlit's `AppTest` on the offline e2e export (renders, filters).
  Hosting (for example Streamlit Community Cloud) needs an account, so it is the
  owner's step (H19). The site links to it only when `ARENA_DASHBOARD_URL` is set.
- Pins in `requirements/dashboard.txt`; `apps/` is now linted.

## 2026-11-13 · REST API and Docker compose (T150)

- `arena api` (FastAPI): /health, /questions (filters), /questions/{id}, /leaderboard
  (per topic; official record once it starts, else rehearsal with its label) and /sql
  (one read-only SELECT via the same locked DuckDB as `arena mcp`). Response models are
  the static JSON API's pydantic models, so both APIs share one schema. OpenAPI at /docs.
- Read-only snapshot loaded at start; no writes, no auth needed, nothing hosted: it runs
  locally (`docker compose up`) and in CI, where the image serves the offline e2e ledger
  and curl checks four endpoints, including that a DROP statement gets 400.
- `requirements/api.txt` (uvicorn; FastAPI was already pinned through MLflow).

## 2026-11-13 · Kubernetes manifests validated on kind (T151)

- `deploy/k8s/`: a Deployment and Service for the read-only API (probes on /health,
  resource limits, no privilege escalation) and a CronJob mirroring the 12:30 UTC
  resolve slot with `concurrencyPolicy: Forbid` (one ledger writer, as in Actions).
- A CI job creates a throwaway kind cluster (helm/kind-action v1, version checked from
  the action's tags: v1.15.2, default kind v0.33.0), loads the image, applies the
  manifests, waits for the rollout, curls the API through the Service and runs the
  CronJob once (offline e2e ledger + `ledger verify`).
- First kind run failed (CrashLoopBackOff): Kubernetes injects service-link variables
  such as `ARENA_API_SERVICE_HOST` for a Service named `arena-api`, and the settings
  reject unknown `ARENA_*` keys by design. Fixed with `enableServiceLinks: false` on both
  pod specs and a Service name outside the prefix; the strict settings check stays.
- Stated everywhere as "validated in CI, not hosted": production scheduling stays on
  GitHub Actions (free); a hosted cluster would cost money (S1, owner rule).

## 2026-11-13 · dbt models over the open data (T152)

- `analytics/dbt/`: dbt-duckdb project. Sources are the four public Parquet files
  (`meta.external_location`), staging views, `fct_scored_forecasts` (clipped Brier per
  resolved forecast) and two marts (daily scores; forecaster x topic). Tests: unique and
  not-null ids, accepted values (domains, outcomes, skip reasons), a foreign key from
  forecasts to questions. `dbt build` runs in CI on the e2e export (21 of 21 pass).
- dbt runs in its own virtual environment (`requirements/dbt.txt`): dbt-common needs
  python-dateutil<3 while the main pins use 4.x. DuckDB is pinned to the same 1.5.6, so
  both read the same files. This file is left out of the combined pip-audit, because the
  combined resolution would conflict by design.
- The Data page "reads the marts" by executing the same mart SQL files in DuckDB at site
  build (`ref('stg_x')` resolves to the table `x`), so the published numbers come from
  the dbt definitions without making dbt a dependency of the daily jobs. A unit test
  checks that the marts agree with the scoring code (clipping included).

## 2026-11-13 · Airflow DAGs mirroring the jobs (T153)

- `orchestration/airflow/arena_dag.py`: three Airflow 3 DAGs (morning, resolve, weekly)
  that run exactly the CLI commands and the UTC schedules of the GitHub Actions
  workflows, sharing one pool so only one job writes the ledger (like the shared
  concurrency group). The morning run times out at the 09:30 lock as a second guard;
  the lock itself is enforced inside `arena daily morning`.
- Validated, not deployed: a CI job installs Airflow 3.4.0 with Airflow's official
  constraints file in its own virtual environment and parses the DAGs with DagBag
  (no import errors; task order, schedules and pool checked). A unit test in the main
  suite checks that every DAG command also runs in the matching workflow. Production
  scheduling stays on GitHub Actions (free; a hosted Airflow would cost money).
- API taken from the installed package (`airflow.sdk.DAG`, the standard provider's
  `BashOperator`, `airflow.models.dagbag.DagBag`), as recorded in SOURCES.

## 2026-11-13 · German summary (T141)

- `de.html` with `<html lang="de">` (the shared English header and footer carry
  `lang="en"`), linked as "Auf Deutsch" (hreflang) from every footer, plus a German README
  section. Live counts come from the ledger; the page states that a native speaker has
  not proofread it yet (H17), and repeats the "research project, not advice" notice.

## Proposals for the human

Ideas outside the specification. The agent lists them here and does not build them.

- **Open public participation ("players vs AI vs ML"), owner question 2026-11-12.** Today
  anyone in any country can *view* the site; nobody can *submit* forecasts. A free design:
  (1) the owner creates a Google Form (nickname, consent checkbox, one probability per
  question) whose responses sheet is published as CSV; (2) questions are published the
  evening before (about 18:00 UTC) instead of 05:30, so every time zone gets a window
  before the 09:30 UTC lock; (3) a pre-lock run (about 09:00 UTC) reads the CSV, keeps only
  answers time-stamped before the lock, and writes them to the ledger as player forecasts
  under a random player id; (4) the site gets a players' leaderboard on the same
  questions and scoring rules as the AI and ML forecasters, with a minimum number of
  answered questions before a player is ranked. The ledger stays the database (git +
  hash chain), DuckDB/Parquet serve the analysis; no server or paid database. Needs:
  owner decision (changes SPEC 4 timing and SPEC 8's forecaster list), the owner's form,
  a privacy notice and consent text (GDPR: nicknames are personal data; ledger entries
  cannot be erased later, so players must be told before joining), and an anti-spam
  rule (e.g. one entry per nickname per question, latest valid answer counts).
- **Human panel published only as an aggregate (GDPR).** The ledger is append-only and
  public, so a panel member's pseudonymous entries could never be erased (GDPR Art. 17).
  Safer: write only the panel median per question (the `human_panel` forecast) to the
  public ledger, and keep individual answers out of it (in the owner's form tool, which
  can delete them). Needs a human decision before T092.
- **Template-level base rate for attention.** SPEC 8.1 defines `base_rate` per template
  and entity. For attention the entity is an article that rarely repeats, so `base_rate`
  is always 0.5 there. A template-level variant (same template, any article) would be a
  more informative baseline. Needs a human decision because it changes a SPEC 8 rule.
- **Panel timing (needed before T092).** The batch is sealed by the first morning run
  (~05:30 UTC, SPEC 6), which is also when questions appear, so panel answers given before
  the 09:30 lock cannot join the sealed batch. Options: (a) panel members forecast the
  *next* morning's questions announced the evening before (needs questions generated
  earlier: changes SPEC 4); (b) add a pre-lock run (~09:00 UTC) that appends panel
  forecasts and only then seals (changes when the seal is written; seal still before lock);
  (c) keep the panel out of the batch and publish it as a separate, clearly labelled
  record. The agent recommends (b) with a hard rule that a late run writes nothing.
- **More interesting questions for people to vote on (owner request, 2026-11-12).** The
  owner finds the current questions dry for a human audience. Ideas, in order of how little
  they disturb the record. All need a human decision; any new question type is a new
  template (or `template_version`) added before the official start (SPEC 2.9), never a
  change to an existing one.
  1. *Plain-language titles* (no rule change): every question page already has a
     machine-made title; add a one-line human title such as "Will Berlin hit 20 °C
     tomorrow?" next to the exact resolution rule. The resolution rule stays the source of
     truth.
  2. *"Question of the day" for the panel* (needs the panel timing decision above): pick
     3-5 questions a day for people, chosen by a fixed rule written before the batch
     (e.g. the attention question with the largest recent jump, the closest-to-50/50
     weather question by the `ml` forecast) so the choice cannot be tuned on outcomes (I8).
  3. *Head-to-head weather questions* (new template): "Will Berlin be warmer than Munich
     tomorrow?", "Will it rain more in Hamburg than in Frankfurt?". Same stations and
     source as today.
  4. *Event-style weather questions* (new template): first frost, snow, a "tropical night"
     (minimum >= 20 °C), wind gusts above a storm threshold, from the same DWD data.
  5. *Wikipedia head-to-head* (new template): "Will article A get more views than article B
     tomorrow?" for two trending, non-person articles. Same source and person filter.
  6. *US stock index* (H08): researched 2026-11-12; no free source found whose terms clearly
     allow automated use and publication (S&P index values on FRED are marked
     "reproduction prohibited without prior written permission"). Only with written
     permission from the index owner, which only the human can request (S2).
  The agent recommends 1 now, 2 together with the panel, and 3-4 as the first new
  templates before the official start, because they reuse verified sources.
- **Money-related topics with a usable source (researched 2026-11-12, owner asked for
  topics like stock prices).** Search results only, official terms still to be read
  before building; each needs an account or key, which only the human can create (S2):
  1. *Bitcoin / crypto prices* via CoinGecko: the free Demo plan allows display with
     attribution ("Powered by CoinGecko API"); redistribution of the API itself is not
     allowed. Questions like "Will Bitcoin be above $X at 00:00 UTC on D?". Needs a free
     CoinGecko account and key.
  2. *German fuel prices* via Tankerkoenig (MTS-K data, labelled CC BY 4.0, older AGB
     forbid passing on raw datasets): "Will average diesel in Berlin be above X €/l on D?".
     Needs a free API key; confirm the current terms with Tankerkoenig first.
  3. *Stock prices (US, India, Germany)*: not usable. Index and exchange data (S&P,
     Nasdaq, NSE, DAX/STOXX) need a licence or written permission. Single stocks such as
     Google (Alphabet) are exchange data with the same problem. Publishing daily
     probabilities about named listed shares could also count as an "investment
     recommendation" under the EU Market Abuse Regulation (Art. 20), with disclosure
     duties; get legal advice before ever doing it.

## 2026-11-13 README results and skills are generated (T142)

- Context: T142 asks for a results table and a skills list in the README; hand-typed numbers
  would drift from the model cards (I5).
- Decision: `scripts/readme_sections.py` rewrites two marker blocks from `docs/models/*.md`
  (backtests, labelled as such) and from `arena.site.recruiters.PROOFS`; a unit test runs
  `--check`, so `make check` fails if the README is stale. No live numbers are in the README
  yet (the official record has not started). Screenshots are of the offline demo build and
  say so.
- Alternatives: `arena report cv` output pasted by hand (drifts); live leaderboard in the
  README (empty until the official start; the site already shows it).

## 2026-11-13 Evening publication of questions (T160)

- Context: the players' leaderboard (Phase 6) needs questions public well before the
  09:30 UTC lock; at 05:30 UTC most of the Americas are asleep.
- Decision: a new `evening` job (18:00 and 19:30 UTC on B-1, workflow `evening.yml`)
  publishes batch B's questions; the morning job only fills domains the evening missed and
  runs every forecaster as before. The lock, question texts and resolution rules are
  unchanged. Because thresholds are computed from data as of the evening (for example the
  Wikipedia reference day is a day older), evening questions are `template_version` 2;
  the version is derived from `created_at < batch day`, not from a flag, so it cannot be
  wrong. Methods shows a template-version table (SPEC 2.9 changelog). The evening job is
  refused before 16:00 UTC (the day-ahead auction for B is published around noon UTC) and
  on any day other than B-1. Its run manifest and health report count towards the
  clean-day rule: a failed evening run makes that day not clean (the stricter reading).
  The official record has not started (`ARENA_OFFICIAL_START_NOT_BEFORE` is 2099-12-31),
  so no official question changes version.
- Alternatives: run forecasters in the evening too (rejected: less data, and it changes
  every forecaster's information set); move the lock (rejected: the task says lock
  unchanged, and the lock must stay before the noon auction).

## 2026-11-13 Public players' intake (T161)

- Context: the players' leaderboard needs people's forecasts in the record, with the same
  forecast-before-lock guarantee as the machines, without collecting personal data.
- Decision: a `players` job (09:00 and 09:15 UTC, `players.yml`) reads the published form
  CSV (`ARENA_PLAYERS_CSV_URL`) and appends to a new ledger family `players/B.jsonl`. It
  cannot go into `forecasts/B.jsonl`, which the batch seal makes immutable at about
  05:30. Each player is `player_` + 8 hex of SHA-256 of a random player code (no
  nicknames or emails are read); consent must be `yes`. The latest valid row submitted
  before the run counts; once written, a forecast is never replaced (append-only), so a
  change of mind after the first intake does not count. `ledger verify` checks these
  forecasts against the lock like any other, and `verify --git` checks their commits.
  The scoring loader reads only `forecasts/`, so players never enter the machine boards
  (I4-style separation); T162 adds their own board, with at least 10 resolved answers
  before a player is ranked.
- Alternatives: nickname-derived ids (rejected: guessable from the nickname, personal
  data); HMAC with a secret salt (rejected: needs a new secret and players could not find
  themselves); replacing earlier records (rejected: I2).

## 2026-11-13 Anthropic adapter re-sends content blocks exactly (bug fix)

- Context: the first live morning run recorded `error` skips for every sampled `agent`
  question: the API rejected the replayed assistant turn because a thinking block was
  modified (our serializer dropped null fields).
- Decision: re-send `block.to_dict()` (the SDK's exact wire form). This is a bug fix, not
  tuning (I8): no prompt, model or threshold changes, and it was found from an API error,
  not from any outcome; the version strings stay the same. The recorded skips remain.

## 2026-11-13 Frequent scheduled runs behind a due-gate (T180)

- Context: on the first live day GitHub started every scheduled run about 8 hours late:
  both morning runs (05:30, 07:00) started after the 09:30 lock, so the batch exists only
  because of a manual run; the 18:00 evening run had not started by 19:29.
- Decision: schedule morning hourly 00:15-08:15 UTC, evening hourly 16:00-23:00, resolve
  every 3 hours, players at 08:40/09:00/09:15. A small `gate` job runs
  `arena schedule due --job <job> --sync` (pure function of clock and ledger) and the
  real job runs only when there is work; manual dispatches always run. Gate-only runs
  write nothing to the ledger. The lock and every job's own rules are unchanged.
- Consequence: forecasts can be made earlier than 05:30 (as early as 00:15) when GitHub is
  on time. That is still before the lock (I1) and the time is recorded on every forecast;
  the information set is whatever was public then (I3). With the shared concurrency
  group, a newer queued run can replace an older pending one; the frequent schedule makes
  that harmless.
- Alternatives: an external scheduler calling `workflow_dispatch` (needs an account,
  human item); moving the lock (rejected: SPEC and the noon auction).

## 2026-11-14 T190 result: caching and structured outputs both stay off live

- Same golden set (12 items, seeded), same model, run on 2026-11-14 00:52 UTC; results in
  `evals/results/eval-20261114T0052-{text,structured}.json` (both runs started in the same
  minute and share a run id; the file names tell them apart, and the harness now ids runs
  to the second). The page and `docs/interview/numbers.md` show every figure.
- **Structured outputs** (schema-constrained answers, version suffix `|so`): the first
  attempt (2026-11-13) failed on every call because the schema sent to the API carried
  `minimum`/`maximum`/`maxLength`/`maxItems`, which the API does not accept; fixed by
  sending a schema without them (`anthropic_schema()`; ranges are still checked after the
  call). The second attempt ran. It was not better: `llm_context` first-try valid JSON fell
  to 83% (two answers needed a repair, a rule the schema cannot express) and its Brier score
  was higher than in the text run; `llm_plain` was also higher. With 12 items none of this
  is a ranking (intervals include zero), but there is no evidence for switching. It stays
  off live; the capability and its tests stay in the code, labelled as evaluated.
- **Prompt caching** (automatic): for these one-shot calls each prompt differs, so almost
  everything was written to the cache (billed at 1.25x) and little was read back. Against
  the earlier uncached run on the same sampled items (`eval-20261113T1206`) the estimated
  cost of `llm_context` was higher and `llm_plain`'s about the same (both runs of
  2026-11-14 used the cache). The Brier scores of identical configurations also differ
  between runs, which shows how much noise 12 items carry. Off by default in the morning
  and eval workflows (`ARENA_LLM_CACHE=0`); the eval workflow has a `cache` input to
  re-measure. It may still pay for the multi-turn agent loop, which has not been measured.
- Two metric bugs found on the way, both fixed: an all-errors run reported 100% valid JSON
  (provider errors now leave the denominator), and result files did not say why a call
  failed (rows now carry the first 300 characters of the error).

## 2026-11-14 OTLP/JSON export and a Polars cell (T191)

- OpenTelemetry: the call spans (T123) are also published as OTLP/JSON (`data/otlp/`, one
  file per batch day, `llm/otlp.py`), written by hand against the OTLP specification and the
  GenAI conventions (docs/SOURCES.md) instead of adding the OpenTelemetry SDK: the spans
  already exist, the export is a pure function of them (deterministic ids), and no new
  dependency is needed. The site says "OTLP/JSON export", not "OpenTelemetry
  instrumentation", because nothing is instrumented through the OTel SDK.
- Polars: one notebook section recomputes the Brier table from the Parquet files and fails
  the CI notebook run if it disagrees with DuckDB. Pinned in `requirements/nb.txt` only
  (notebook extra; not in the core lock), installed by the CI a11y job that runs
  `make notebook`.


## 2026-11-15 Audit repairs (T193)

The owner requested implementation of the audited handoff. Preserve ledger bytes,
question meanings, clipping/statistical thresholds, the promotion rule and the owner-controlled
official not-before date. Repair missing execution paths and enforce the registered coverage
and evidence requirements. Do not backfill historical ML forecasts.

- ML inference uses each domain's promoted champion; unavailable or invalid artifacts produce
  explicit skips. Candidate inference failures disqualify that candidate on the fixed evaluation
  population instead of deleting questions for healthy models.
- Missing required common-set members make the headline incomplete. Hypotheses with absent
  comparisons or inconclusive evidence remain undecided; no equivalence margin is introduced.
- Public SQL exports omit excluded resolutions but retain source revisions' first outcomes,
  matching the canonical scorer. APIs preserve that outcome and expose revision diagnostics.
- Provider refusals carry structured usage to the guard. Unreported attempts reserve their
  estimated input plus full output cap in a separately named reserved_tokens field, while
  unreported_requests distinguishes this from provider-reported zero usage. Cache and reserved
  tokens count after restarts. Production adapters disable hidden retries; explicit compatible
  adapter retries reserve allowance for all possible attempts and report actual attempts.
- Workflow completion evidence is recorded independently from application manifests so missing
  setup/finalization and deployment failures cannot be assumed healthy. Historical ledger
  records remain readable and are never rewritten to add new fields.

## 2026-11-19 T220: backtest slices without negative-price days

- Context: the audit asked for Brier by template, season, holiday and negative-price days.
- Decision: `arena.backtest.slices` splits the stored power backtest records by template, month of
  the target day and target-day type (weekday, weekend, German national holiday), pairs `ml` with
  `persistence` on the same questions and uses the existing day-block bootstrap. Negative-price days
  are left out: the stored records do not carry realised prices, and re-reading the source data
  would add a second data path to a backtest card. Slices under 20 questions are never described.
- Alternatives: re-running the backtest with price metadata (rejected: changes the committed run);
  a combined season variable (months are finer and need no extra rule).
- Note: `docs/models/power-slices.md` is generated by `scripts/slices.py`, and a unit test checks
  that the committed card equals what the stored run produces.

## 2026-11-19 T222a: no SMARD forecast-vintage archive yet

- Context: the audit proposed archiving SMARD wind, solar and load forecasts with their fetch
  time so that a leakage-safe renewables ablation becomes possible.
- Finding: the questions lock at 09:30 UTC on batch day B and ask about delivery day B+1. The
  SMARD forecast series (123, 3791, 125) showed no values for B+1 at 16:06 UTC on B, and the
  latest chunk's `created` time (17:06 UTC the day before) suggests a daily update in the
  afternoon. One observation, not proof. If true, the target day's forecast does not exist
  before the lock, so it cannot be a feature, and an archive fetched in the morning would only
  hold forecasts for B. The spec lists no forecast load series either.
- Decision: do not build the archive as specified. T222b first measures the publication time
  (7 days of manifest warnings, no new ledger family, no model change). I8 stays intact.
- Alternatives: archive anyway (stores data the lock rule forbids using); move the lock later
  (changes the research design; owner only).
- Proposal for the owner: if D+1 forecasts turn out to appear only after the lock, drop the
  "missing renewables" caveat from the pitch and say instead that the target-day renewable
  forecast is not available before the lock, which is why the model uses calendar and price lags.

## 2026-11-19 T220: the slice-card reproduction test skips without the stored run

- Context: CI failed on the first slice PR because the test re-reads `backtests/<run>/forecasts.jsonl`,
  which is git-ignored and exists only on the machine that ran the backtest.
- Decision: the byte-for-byte check of `docs/models/power-slices.md` against the stored run now skips
  when the run is missing. CI still checks that the card names the same run as `power.md` and holds
  all three tables. Backtest runs stay uncommitted (I4: they live in their own place).

## 2026-11-19 T090/T093: the ensemble is built, tested and inactive by rule

- Context: SPEC 8.6 asks for a logistic regression on the other forecasters' logits plus domain
  indicators, retrained weekly on official-record forecasts only, active from 300 resolved
  common-set forecasts.
- Decision: `forecasters/ensemble.py` takes the common-set members (`COMMON_GROUP`) as features
  (probabilities clipped to [0.01, 0.99]) and one indicator per domain. The model for a week is fitted
  from rows of batch days up to 2 days before that ISO week's Monday and from the official start on,
  so rehearsal days never train it and every training outcome was known at the fit. A question
  becomes a row only if every member forecast it. The job passes the forecasts already written for
  the same question as `ctx["peer_forecasts"]`; the ensemble is listed last. A missing member or an
  unseen domain is a `model_missing` skip. Below the threshold it is simply not registered (inactive is
  not a failure), so the health roster is unchanged until it has run once.
- Alternatives: fit at forecast time on everything resolved so far (rejected: not weekly, and it moves
  daily); include `persistence` and the local/graph LLMs (rejected: not in the registered common set,
  and sampled forecasters would shrink the training set).
- Status: it cannot activate until the owner sets the official-start date, so T093 waits.

## 2026-11-19 T222b / T223b: measurement step and agent variant in the eval

- The SMARD probe only reads and prints; it adds no ledger family and feeds no model (I8). It runs
  after the morning and evening jobs with `continue-on-error`, so it can never fail a job.
- The eval agent has series and base-rate tools only: a replay of a past day has no as-of news or
  Wikipedia snapshot, and offering today's news would leak (I3). Its result will be labelled that way.

## 2026-11-19 T230: website usability decisions

- Race chart: only from 7 days of results (fewer points are noise); three coloured lines (ML model, base rate,
  best AI forecaster), the others grey; values in a sorted legend instead of colliding end labels; separate phone layout.
- Home: six cards chosen by `pick_cards` (most forecasters answered, then most disagreement, spread over topics);
  rows with no forecast replaced by one line. Display only; no number changes.
- Leaderboard: reordered and folded; the statistics and labels are unchanged. The "supported" wording under a
  "too early to tell" label is left for the owner (H25, SPEC 10).
- Public text no longer names owner items (H15, H20); the Status schedule describes the real gated hourly runs.
- Tests: browser checks for chart text (inside its picture, at least 10.5 px as rendered), the archive state filter and
  page width; the leaderboard heatmap test opens the disclosure first.


## 2026-11-20 T232: page polish keeps one component set
- Context: owner found the reference pages (Backtests first) "very basic": default-styled contents links, stuck-together paragraphs, a duplicated link list.
- Decision: restyle shared components only (contents chips, callout `.banner`, `.prose-card`, `.chips`, card spacing) instead of a new layout per page; at-a-glance chips on model cards are copied from the card text (`cards_page.card_stats`), never computed or typed, and absent when the card lacks them (I5).
- Alternatives: a dark hero on every page (rejected: competes with the home hero and adds height); hand-written summaries per card (rejected: numbers could drift from the card).

## 2026-11-20 T233: spacing is a zero-specificity layer, not per-page margins
- Context: boxes touched wherever a template forgot a margin (home, recruiters, findings, play).
- Decision: `:where(main > .wrap, .game) > * + *` and the same inside cards give every block the same gap, and any component that sets its own margin still wins; a browser audit (`tools/a11y/layout.js`) keeps it that way.
- Rejected: a sticky contents rail for long pages (narrows tables and the six-step diagram; the chip list is compact enough); rewriting each template's margins one by one.

## 2026-11-21 T234: dates are wrapped in the built HTML, not in the templates
- Context: tables broke dates and model versions at their hyphens ("2026-" / "11-21").
- Decision: one post-processing pass (`site/typography.nowrap_dates`) wraps ISO dates in the page body text in a no-break span; attributes, the head and scripts are never touched, and tests that compare page text strip the span.
- Rejected: non-breaking hyphens in the text (changes what is copied and searched), per-template spans (easy to miss).

## 2026-11-21 Experiments lab approved by the owner (Phase 14)
- Context: the owner asked to add fine-tuning (QLoRA) and other techniques used in industry, so a hiring manager sees broad experimentation; the repo rules ask for owner approval for features outside the SPEC (AGENTS.md section 3).
- Decision: the owner approved the plan in chat on 2026-11-21: GPU work on a free Colab T4 that the owner starts; up to about US$2 in total for paid Claude calls (distillation labels, LLM-as-judge), each as a capped manual run; the full program; a new Lab page plus model cards. SPEC section 17 adds the lab rules L1 to L7. Standing approval 2 in CLAUDE.md does not cover non-forecast API use, so H27 must be ticked before those two workflows are committed.
- Alternatives: a smaller top-5 program (rejected by the owner); results in docs only (rejected: the owner wants a Lab page).

## 2026-11-21 T244: fine-tuning with a small in-house loop, not TRL
- Context: the plan named TRL's SFTTrainer. The target here is a single answer token (YES or NO), so supervised fine-tuning is a binary cross-entropy on the logit difference of two tokens.
- Decision: a 100-line loop in `arena.lab.finetune.train` (PyTorch plus PEFT); no TRL. It is unit-tested on CPU with a tiny random Qwen2 model, avoids TRL's frequently changing API, and keeps the memory low by asking the model for logits at the last position only (`logits_to_keep=1`). New dependency: `peft==0.22.0` (Apache-2.0) in `requirements/lab.txt`; `bitsandbytes` is installed only in the Colab notebook.
- Alternatives: TRL SFTTrainer (more moving parts for a one-token target), Unsloth (not needed, adds a dependency), full fine-tuning (does not fit a 16 GB T4 for 1.5B: about 18 GB for weights, gradients and Adam states).
- Note found while building: the live prompts are about 2,300 Qwen tokens (numbers tokenize into many tokens), twice the first estimate, so the pre-registered run trains on 2,000 rows and uses a 2,560-token limit.

## 2026-11-21 The lab goes live (Phase 15): owner decisions
- Context: the owner asked that the fine-tuned model and the other lab techniques run as real forecasters, not only as separate experiments ("all these things can be deployed in this project").
- Decision (owner, in chat): (1) the fine-tuned model runs live as `llm_local_ft` whatever its backtest result is, frozen and pre-registered, labelled experimental; (2) the daily LLM token cap goes from 150,000 to 300,000; (3) all lab techniques also run live: cascade router, agent with hybrid retrieval and guards, weekly challengers (global LightGBM, Chronos-2), live monitoring on Status. SPEC 17 L1 is amended and the shadow-forecasting tasks T249 and T263 are superseded.
- Integrity: integrity rules I4 and I8 stay. Backtest first, then freeze the version and go live, as `ml` did; the model is trained on replayed days up to 2026-06-30 only. New forecasters have their own ids and versions, stay out of `COMMON_GROUP` and the ensemble, and follow the same sample, skip and budget rules (I6).
- Alternatives: keep everything offline (rejected by the owner); go live only if the backtest is not worse than `llm_local` (rejected by the owner: a loser is also a result).

## 2026-11-21 T272: three more series colours
- Context: the chart palette had eight validated slots; the three experimental forecasters need their own.
- Decision: slots 9 to 11 (teal, brown, olive; light and dark values) added to the stylesheet. They have not been checked for colour-blind separation like slots 1 to 8, so the forecaster name is always written next to the line (legends and labels), never colour alone.

## 2026-11-21 Monthly retrain of `llm_local_ft` on the owner's Mac
- Context: the owner asked why the fine-tuned model is not retrained automatically and chose their own machine (MacBook Air M5, 16 GB) with a monthly schedule over paid GPUs. Colab cannot be scheduled.
- Decision: retrain rule pre-registered in `lab/prereg/qlora-retrain.md`: replayed data only, promote only if not worse on a held-out window, promotion is a PR the owner merges. The Mac recipe is MLX LoRA (bitsandbytes is CUDA-only), accepted only after a smoke run.
- Alternatives: paid GitHub GPU runner or rented GPU (needs spending and an account, not pre-approved); daily Colab (manual); retrain weekly (versions too short-lived to evaluate).

## 2026-11-21 T277: ONNX export of the LightGBM power models
- Context: serving parity for the deployed container, no joblib or LightGBM needed at inference.
- Decision: `forecasters/onnx_power.py` exports `power-lgbq` and `power-glgbq` with onnxmltools 1.16.0 (Apache-2.0) and serves with onnxruntime 1.31.1 (the version rag.txt already pins) (MIT); `POST /predict/power` in the API (503 without `ARENA_ONNX_DIR`). New files `requirements/onnx.txt` (export, CI) and `requirements/serve.txt` (runtime, Docker). Parity tolerance 1e-4 (float32 trees give about 1e-6 on quantiles), not 1e-6 as first planned.
- Not done: the live champion `power-gbq` (scikit-learn HistGradientBoosting, quantile loss) does not convert with skl2onnx 1.20.0 (checked 2026-11-21, `TreeEnsembleRegressor` node cannot be built), so it stays on joblib. The ONNX hash is in the exported manifest, not yet in the weekly registry metadata; Docker CI proves the route and the runtime import, the numeric parity is proven by the unit tests in the `check` job.
- Alternatives: convert the champion by hand (risk of silent mismatch); export only to a file without an endpoint.

## 2026-11-21 T279: `experimental` input on the morning dry run
- Context: the experimental forecasters are switched by repository variables, which the agent cannot set or read; the launch plan needs a measurement of runner time and tokens before any variable is turned on.
- Decision: `morning.yml` gets a boolean `experimental` input that sets `ARENA_AGENT_HYBRID=1` only when `dry_run` is also true. A live run can never be switched on by it; scheduled runs ignore it. `llm_local_ft` is not measurable until its artefact is pinned (H26/H28).
- Alternatives: dispatching from a branch (not allowed); asking the owner to set the variable first (turns it on for live runs before measuring).

## 2026-11-21 T259: Chronos-2 as a backtest benchmark
- Context: the owner asked for the remaining lab tasks in one PR; Chronos-2 is the newer foundation model next to Chronos-Bolt.
- Decision: `ts_chronos2` joins the power time-series benchmarks (backtest only, zero-shot, revision pinned). It is not a live forecaster or a weekly challenger: the 120M-parameter weights would need a registry artefact and a per-question model call inside the lock-critical morning run, which T275b leaves open until the backtest says it is worth it.
- Alternatives: weekly challenger now (cost and risk without evidence); TimesFM (licence and CPU feasibility not checked).

## 2026-11-21 T258: the global LightGBM does not beat the champion
- Context: one LightGBM per quantile level over all five statistics (`power-glgbq`) was backtested over 365 days (run recorded in `docs/models/power-global.md`).
- Result: Brier 0.2079 against 0.1930 for the champion, difference +0.0149 [+0.0097, +0.0198], so worse with an interval that excludes zero. Not tuned (defaults, no Optuna), which is part of why it is weaker than the tuned per-statistic LightGBM.
- Decision: no live change (I8). It stays a weekly challenger; the weekly rule promotes it only if it ever scores no worse than the champion on the recent window.

## 2026-11-21 T275b: Chronos-2 is not made a weekly challenger
- Result (T259 backtest, 365 days): Chronos-2 zero-shot Brier 0.2073, Chronos-Bolt 0.2142, persistence 0.2205, champion 0.1930; Chronos-2 minus champion +0.0143 [+0.0045, +0.0235].
- Decision: it stays a backtest benchmark. A 120M-parameter model per question in the lock-critical morning run, plus a registry artefact, buys nothing while it is significantly worse. Reopen if a later backtest changes the picture.

## 2026-11-21 T284: CI `check` job timeout 15 -> 25 minutes
- Context: the push CI on the merge of PR #27 was cancelled by the job's own 15-minute limit (install about 2 min, `make check` about 13 min), so `promote` was skipped and `stable` did not advance. The same code passed on the PR run (check 13 min).
- Evidence (local, 763 tests, 8 min): the slowest tests are the weekly-job tests in `tests/unit/test_weekly.py` (9 tests, about 3.5 min together), then the ONNX, global-LightGBM and SHAP model tests (8-12 s each); the new lab tests are not the cause.
- Decision: raise only the `check` job limit to 25 minutes. No tests removed or weakened. Splitting or slimming `test_weekly.py` is a possible later proposal.
- Alternatives: delete slow tests (rejected: loses coverage); run tests in parallel (needs `pytest-xdist`, a new dependency).

## 2026-11-22 T245/T246: the QLoRA run is evaluated from its Colab scores; GGUF parity missed the limit
- Context: the owner ran the notebook on a free T4 and published release `lab-qlora-r1` (GGUF SHA-256 checked against the release digest). The first real llama.cpp scoring run exposed a bug in `LlamaScorer` (it read a per-position logits table that llama-cpp-python only fills with `logits_all`); it now reads the last token's logits and a regression test covers it.
- Decision: no `lab-eval.yml`. The Colab score files already contain per-question probabilities for all four variants, so `arena lab ft-eval` builds the result on identical items (paired day-block intervals against the untuned model, the base rate and the `ml` backtest). The GGUF is checked on a subset (`arena lab ft-parity`, every 9th test row, 31 rows).
- Result: pre-registered H-FT1 holds (tuned beats untuned), H-FT2 holds (does not beat `ml`), H-FT3 does not hold on the subset (Brier +0.0123 against a 0.005 limit; 31 rows is noisy, margin correlation 0.62). The tuned 1.5B model is also worse than the base rate; the 0.5B LoRA model is better than the 1.5B QLoRA model. Reported as is; nothing was tuned after seeing it.
- Open: whether the GGUF goes live as pinned, is first calibrated on its own validation margins (a few hours of CPU in a manual workflow), or waits (H32). The Colab run used transformers 4.57.6, not the pinned 5.22.2; the card says so.

## 2026-11-22 T246b: calibrate the GGUF on its own validation margins (owner chose option b)
- Decision: a manual workflow `lab-eval.yml` scores all validation and test rows with the pinned GGUF on four parallel free runners (each about 200 rows at about 30 s per row) and prints each shard's margins in its log; `arena lab ft-calibrate` merges them and refits the Platt map on the validation margins only (rule L3), reporting Brier of the old and the new map per split. Dispatch happens from `main` after the PR is merged (one dispatch, no secrets, no ledger write). The new map is pinned in a small follow-up PR, which changes the version string.
- Why logs and not artifacts: the artifact download action's current major version was not looked up (AGENTS.md section 7) and the agent cannot download workflow artifacts here; log lines avoid both.
- The result is reported whichever way it goes; going live still waits for the owner's reply after seeing it (H32).

## 2026-11-22 T271: `llm_local_ft` goes live now (owner decision)
- Context: the owner decided twice that the fine-tuned model runs live whatever its result ("whatever the backtest result", then "you can also go live fine tuned model" after seeing the evaluation: worse than the base rate, GGUF parity missed the limit).
- Decision: `ARENA_LLM_LOCAL_FT` defaults to `1` in `morning.yml`, so it publishes from the first morning run after the merge, with the pinned Platt map (fitted on the Colab margins). It is experimental, in no headline board and not in the ensemble; every failure (missing runtime, download, hash, load, time budget) is a `model_missing` or error skip with a reason, never a default probability (I6). The model is frozen (I8): when T246b pins a map calibrated on the GGUF's own validation margins, that is a new version string with its own record, decided before the live results of the old one are looked at.
- Honest expectation, written before the first live day: its live Brier will probably sit near or above the base rate and well above `ml`; the live board will say so.
- Switch off: set the repository variable `ARENA_LLM_LOCAL_FT` to `0` (the agent cannot change repository variables).

## 2026-11-22 T246b: the first lab-eval run failed because the scoring runners have no PyTorch
- Context: all four shards of `lab-eval.yml` (run 45008783161) failed in under a second at `arena lab ft-score`: `ft_gguf.py` imported `finetune.train`, which imports torch at module level, and the shard jobs install only the lock and local-LLM requirements.
- Decision: the import moves into `calibrate()` (run locally, where torch exists). A unit test imports the whole scoring path in a subprocess with torch blocked and reads all 828 rows, so a torch import on that path fails CI. No workflow change needed; the run is dispatched again after the merge.

## 2026-11-22 Phase 16: production skills (owner decisions)
- Context: the owner showed a chart of skills in 2026 AI-engineer postings and asked for the production skills the project lacks, as used in German and US AI/ML/DS product companies.
- Decisions (owner, in chat): cloud as code and run locally (Terraform for AWS validated in CI and an S3 path tested against MinIO; no account, no spending, so labelled "not deployed"); add all of Qdrant, bandit/online learning, unsupervised learning, observability and TypeScript; LLM work: DPO preference tuning (the owner runs it on Colab), offline prompt optimisation, self-consistency and the LLM judge (paid runs each need the owner's OK). "Something else" was ticked without a named item: nothing extra is added for it.
- Rules: each new technology gets a SOURCES line (version, licence, docs checked that day) and a DECISIONS line; anything that forecasts is a new experimental forecaster id (frozen version string, no headline board, not in the ensemble); servers (Qdrant, MinIO, Jaeger, Prometheus) run only in CI jobs or `make smoke-*`, never in `make check`.

## 2026-11-22 T293: `bandit_hedge` (Hedge expert advice) replaces "reinforcement learning" with its honest form
- Context: there is no environment to explore in a forecasting benchmark, only delayed feedback on how each forecaster did, which is the expert-advice / bandit setting.
- Decision: Hedge weights per topic from the Brier losses of resolved questions at least two batch days old (a pure function of the ledger, so restartable), blend of the peers' probabilities; Thompson sampling only in the replay study. Registered behind `ARENA_BANDIT` (default off), experimental, no headline board, not an ensemble member.
- Result of the replay on the live record (5 days): better than the equal-weight mean, not better than `ml`; reported as a mechanism check with wide intervals.

## 2026-11-22 T294: two unsupervised experiments, both with negative results, published
- Anomaly detection (`ops/anomaly.py`, `lab/anomaly_study.py`): an Isolation Forest fitted on 27 days finds fewer injected faults than a robust z-score (spike 56.6% vs 100%, unit error 28.7% vs 69.7%, flat feed 1.6% vs 18.9%, repeated day 9.8% vs 10.7%; false alarms 4.1% vs 7.4%). Decision: Status shows both with thresholds fixed on 2019-2024 clean windows; nothing fails a run (informational like the data contracts).
- Regimes (`lab/regimes.py`): k-means on standardised 24-hour shapes, k=2 by silhouette (about 49%/51% of days); adding the last day's regime to the champion's 37 features changes the pinball loss of tomorrow's mean price by -0.022 [-0.161, +0.107]: no demonstrable gain, so no `ml_regime` challenger is built.

## 2026-11-22 T291: Qdrant as a vector database; not switched on in the live agent
- Decision: `agent/vectorstore.py` adds `QdrantIndex` with the same `search` contract as `PastQuestions`; the leakage rule (`resolved_ts < asof`) is a payload filter inside the store. New pinned file `requirements/vectordb.txt` (qdrant-client 1.20.0 and its five new transitive packages). Unit tests run in local mode in `check` and, in the CI job `vectordb`, against a Qdrant v1.20.2 server.
- Result (`arena lab vectordb`, local mode, 143 queries): nDCG@5, MRR and precision@5 are identical to brute force and the top-5 id set is the same for 100% of queries. Local mode is not an HNSW index, so it gives no speed-up (p50 96 ms against 40 ms in this run); a server benchmark is a CI-log item, not a claim.
- Not done on purpose: the live `agent` keeps its in-memory retriever. Adding a network service or a new package to the lock-critical morning run is a retriever version change (I8) and the dense results are identical anyway, so there is nothing to gain yet; the owner can ask for it.

## 2026-11-22 T295: Prometheus metrics and Jaeger traces, tested against the real servers in CI
- Decision: `/metrics` on the REST API with `prometheus-client` (added to `requirements/api.txt`, so the Docker image has it). Labels are route templates, never ids (bounded cardinality); each app has its own registry. A new CI job runs Prometheus and Jaeger as containers on the host network and checks that the scrape shows the request counter and the ledger gauge and that Jaeger stores the three sample spans exported with the OpenTelemetry GenAI attribute names. Arize Phoenix (T255b) stays blocked on H34; Jaeger is the trace viewer that could be verified.
- Not claimed: dashboards or alerting rules (nothing is deployed for them to run on).

## 2026-11-22 T296: the site's script is written in TypeScript and compiled to the same single file
- Decision: `site_ts/app.ts` is the source; `src/arena/site/static/app.js` is its committed, generated output (the site stays one self-hosted file, no bundler, no runtime dependency). `make site-ts` compiles; CI recompiles and fails on any difference, so the two cannot drift. Strict mode with no `any`.
- Alternatives: a bundler such as Vite or esbuild (more tooling than a 350-line file needs); leaving JavaScript (the posting-skills chart lists TypeScript).

## 2026-11-22 Phase 17 requested by the owner: pandas, more topics, crypto, under EU and German rules
- Owner request (in chat, mid-work): add pandas, and other technology or topics such as crypto that make the project more interesting, following EU and German rules.
- Decision: recorded as T301 (pandas, as an interface next to Polars and DuckDB, not a replacement), T302 (new open-data topics, terms read first, rehearsal-only until 30 days) and T303 (crypto, blocked on the owner's CoinGecko key H12; no trading, no real money, not-advice notice, attribution). Nothing in the safety rails changes: S1 (no money), S2 (no accounts), S7 (source terms), S12 (research, not advice, no personal data).

## 2026-11-22 T292: AWS as code, not deployed; S3 path tested with moto
- Decision (owner: "AWS as code, run locally"): Terraform in `infra/aws` for a private S3 bucket served through CloudFront (origin access control), an ECR repository, an ECS Fargate service behind an ALB, a log group, task roles without permissions, and a monthly budget alarm. Nothing is applied: no account, no spending (S1, S2). CI formats and validates it. A budget alarm and an HTTP-only listener are stated limits; a certificate and a custom domain are listed as left out.
- `arena site publish-s3` uploads a built directory (content types, cache headers, skip unchanged, prune, dry run) and is tested with real boto3 calls against moto. A MinIO container was planned and dropped because the image is no longer on Docker Hub.
- The AWS provider documentation was not readable from this environment, so resource arguments follow the provider's well-known 6.x schema from memory and are checked only by `terraform validate` in CI; if that fails, the CI log shows the exact argument to fix.

## 2026-11-22 T301: pandas as an interface, not a replacement
- Decision: `analytics/frames.py` gives pandas views over the scored record (same numbers as `scoring.leaderboard`, a test proves it); pandas is imported inside the functions so the production jobs, which do not install it, never load it. DuckDB and Polars stay the query engines. pandas 2.3.3 is already pinned (`requirements/ml.txt`, via scikit-learn and MLflow tooling).
- `lab/stacking_study.py` shows the DataFrame stack end to end (ColumnTransformer + Pipeline + LogisticRegression, walk-forward). A first replay on the live record had only 2 test days (32 questions), so no result is published; the command refuses to write a result below 5 test days (T301b waits).

## 2026-11-22 T298/T299: self-consistency as an evaluation variant; DPO reduces to a margin loss
- T298: the Anthropic adapter does not send a temperature (current models reject it), so self-consistency relies on the provider's default sampling: five calls of the same prompt, mean probability, spread recorded. Evaluation variant only (`llm_context_sc5`, five times the tokens), never live; the paid run waits for the owner's OK (H36).
- T299: for a one-token YES/NO answer the log-probability difference is exactly the logit margin, so DPO is `-log sigmoid(beta * s * (m - m_ref))` and needs only the untuned model's margins on the training rows (computed once). It reuses the QLoRA training loop, data and budget, so the comparison is clean. Pre-registered hypotheses expect the same negative result as QLoRA.

## 2026-11-22 No pollen topic; crypto assessed under EU and German rules
- Owner decision (in chat): do not add the DWD pollen topic. T302 is closed without a new topic; the DWD terms stay recorded in SOURCES.
- Owner question: can crypto forecasts be offered under EU and German rules? Assessment (agent, not legal advice): yes, with conditions, as written in HUMAN_TODO H12 and `docs/COMPLIANCE.md` (free general forecasts, no trading or recommendations, not-advice notice, CoinGecko credit, honest record, complete Impressum, no personal data). The domain stays off until the owner completes H12; switching it on is then a repository variable the owner sets.

## 2026-11-22 GGUF calibration pinned (T246b): the live fine-tuned model has no measurable edge
- Context: owner chose option (b) of H32 (calibrate on the GGUF) and to go live whatever the result. Four CPU shards of `lab-eval` scored all 828 validation and test rows with the pinned GGUF.
- Decision: pin the Platt map fitted on the GGUF's own validation margins only (a=0.5903, b=0.1730; the test sets played no part in the choice). The old map came from the Colab 4-bit model and was wrong for the quantised model (test_nov Brier 0.2508 with it, 0.2473 with the new one). The forecaster version string changes (`platt-0.5903-0.1730`), so the record shows the change; history of other forecasters is untouched (I8: chosen on validation and replay, not on live results).
- Result, reported as is: test Brier 0.2474 (276 questions) for the GGUF against 0.2378 for the Colab 4-bit adapter, 0.2486 untuned, 0.2182 base rate, 0.1663 `ml`; margin correlation GGUF vs Colab only 0.54. H-FT3 (loss < 0.005) is not met (+0.0076). The merge-and-quantise step lost most of the fine-tuning gain; the live forecaster is expected to be near a coin flip. It stays live as an experimental forecaster as decided, and the negative result is the finding (card `docs/lab/qlora-r1.md`).
- Alternatives: keep the Colab map (worse and not fitted to the deployed model); drop the forecaster (the owner decided otherwise); try Q8_0 or fp16 GGUF as a new artefact version (proposal: a Q8_0 export is a cheap next run, 1.6 GB, if the owner wants the gain back).
- Cost: US$0 (Actions CPU).

## 2026-11-22 Prompt optimisation design (T297) and lineage record (T248)
- Context: the owner chose prompt optimisation (offline, free) in Phase 16. Every candidate costs CPU time on the open model (about 30 s per question), so a search over hundreds of prompts is out of reach.
- Decision: a small, pre-registered search: 4 instruction variants x {0, 4} shots = 8 candidates, scored by the single-token margin of the free local GGUF on a 48-question validation subsample, selected by cross-fitted Brier (Platt fitted on one half, scored on the other), winner and baseline evaluated once on the frozen test sets. In-house code (no DSPy: its optimisers need many sampled generations and a hosted model). Shots come from the train split only and contain only the question and the answer, because full prompts are about 1,100 tokens each. Ties and anything not strictly better keep the live prompt; no live prompt changes because of the result (I8).
- Lineage: one JSON record per fine-tuned artefact (`docs/lab/runs/qlora-r1.json`) with every hash, the Colab code commit and package versions and both Platt maps in order; a unit test fails when the pin file, the record and the evaluation result disagree.
- Alternatives: DSPy bootstrapped demos (needs paid or slow generations); a larger search (CPU budget); full prompts as shots (context limit 4,096 tokens).
- Cost: US$0 (Actions CPU).

## 2026-11-22 Crypto goes live; new topics join the overall boards after 30 days
- Context: the owner created a free CoinGecko Demo key, stored it as the secret `ARENA_COINGECKO_API_KEY` and asked for crypto to go live (CLAUDE.md approval 7 for this secret is not written yet; the request in chat is the authorisation for this one change, and the agent did not edit CLAUDE.md).
- Decision: morning, evening and resolve pass the secret to the process (a test limits it to those three workflows); the default topics now include crypto. Usage is about 5 calls per run, 40 a day, against 10,000 credits a month.
- Integrity: the official record starts on 2026-11-23, so crypto joins an already running headline. Conservative reading (AGENTS 3, I8): a topic first seen after the official start has its own board from day one and enters the overall boards after 30 days (`scoring.boards.settling_rule`, used by the site, the JSON API and the CLI summary); topics live before the start are unaffected. This protects the headline and changes no scoring formula.
- Regulatory framing (assessment, not legal advice, docs/COMPLIANCE.md, H12): free forecasts, no trading, no recommendation, notice and credit on every page; the Impressum street address (H14) is still the owner's.
- Cost: US$0; the secret is sent only to api.coingecko.com.

## 2026-11-22 DPO result (T299): no gain over plain fine-tuning; no GGUF, not live
- Context: the owner ran `dpo_qwen_forecast.ipynb` on a Colab T4 (release `lab-dpo-r1`, all four asset hashes checked against GitHub's digests, pre-registration hash matches the committed file).
- Result (276 frozen test questions, 46 days, paired day-block intervals): DPO Brier 0.2363; QLoRA 0.2378 (difference -0.0015 [-0.0032, +0.0005]); untuned 0.2486 (-0.0123, excludes zero); base rate 0.2182 (+0.0181, excludes zero); `ml` 0.1663. H-DPO1 and H-DPO2 hold as expected; H-DPO3 is untested.
- No GGUF: the notebook's optional export cell raised `NameError: gc` (my bug, fixed). Because the QLoRA export lost most of its gain, and DPO is no better than QLoRA, a DPO GGUF is not worth another Colab session now; DPO is not a live forecaster. If the owner wants one anyway it needs the export, a CPU calibration run and a new forecaster id.
- Cost: US$0.

## 2026-11-22 Paid lab runs approved (H27, H31, H36): judge, routing study, distillation labels, self-consistency
- Context: the owner approved in chat all four paid lab items and the free CPU ones (the global LightGBM and Chronos-2 rows of the Lab page were already built: model cards `docs/models/power-global.md` and `power-ts.md`; the planned list was stale and is updated).
- Decision: CLAUDE.md standing approval 2 covers the API key for forecasts only, so the owner's chat approval (H27) is the authority for three new manual, capped workflows that send `ARENA_LLM_API_KEY` for non-forecast purposes: `lab-judge.yml` (100 rationales, about US$0.10), `lab-routing.yml` (276 test questions, about US$0.15), `lab-distill-labels.yml` (1,200 training questions, at most 1,300 requests, about US$0.35). The self-consistency run uses the existing `llm-eval.yml` input. Total well under the US$2.00 lab budget (`docs/project/LAB_BUDGET.md`). Each workflow has read-only permissions, a token cap input, and refuses to run its command outside GitHub Actions in code (S8). Results are read back from one compact log line (`JG_SCORES=`, `RT_PROBS=`, `DL_PROBS=`) because the artifact host is blocked from the agent's sandbox.
- Pre-registered before any call: `lab/prereg/routing.md` (rule fixed: pair, delta 0.15, gamma 0.10), `distill.md`, `judge.md`. The judge items are frozen from the public ledger (`lab/judge/items.json`), the judge never sees the forecaster, and the owner labels 30 of them (H29) so the judge is reported with its agreement, not on trust.
- Honest limits: distillation stores only the teacher's probability (rationale text cannot be read back through logs); the student's Colab training (soft-label recipe) needs the labels first and is a later owner step. The router forecaster (T273) is only built if the routing study's hypothesis H-RT1 holds. GGUF validation and test margins are committed (`lab/artefacts/llm_local_ft.margins.json`) so the routing and evaluation numbers are reproducible.
- Cost: no spend yet. All runs are dispatches from `main` after the PR is merged.

## 2026-11-22 Prompt-optimisation result (T297): a better prompt, still worse than the base rate
- Context: pre-registered search (`lab/prereg/prompt-opt.md`), eight candidates scored with the free local GGUF on 48 validation questions (cross-fitted Brier), then one test evaluation. First dispatch failed at once (`huggingface_hub` missing in the shard venv); fixed and re-run.
- Result: winner `i3s0` beat the live prompt on 276 frozen test questions by -0.0076 [-0.0135, -0.0017] (Brier 0.2556 vs 0.2632). Both are worse than a coin flip's 0.25 and than the base rate 0.2182; the Platt maps were fitted on only 48 validation margins per prompt, which is noisy and is the main limit. Solved examples made things worse in every variant.
- Decision: published as a small positive and an honest overall negative. The live `llm_local` prompt is unchanged; adopting `i3s0` needs an owner decision and a new version string (I8). Cost US$0.

## 2026-11-22 Routing study result (T250): the pre-registered cascade saves nothing; a simpler one is a hypothesis
- Context: owner-approved paid run (H31): Claude `llm_context` on the 276 frozen test questions, US$0.1457, all answered. Rule fixed before the answers existed (`lab/prereg/routing.md`).
- Result: the primary `pair` rule (mean of `ml` and the open fine-tuned model when both are decisive and agree) escalates every question, because the GGUF model is never decisive. H-RT1 (at least 30% saved) is not met and H-RT2 (it escalates almost everything) holds. A live `llm_router` (T273) is therefore not built, as the pre-registration says.
- Findings worth keeping: Claude's probabilities are clearly better than the base rate on these questions (Brier 0.1802 vs 0.2182, interval excludes zero) and not distinguishable from `ml` (0.1663; difference +0.0139 [-0.0166, +0.0433]). Descriptively, answering with `ml` alone when it is decisive and escalating the rest (delta 0.15) avoids 76% of the paid calls at Brier 0.1565, better than either alone. That rule was picked from a grid after the fact, so it is a hypothesis: a new pre-registration with a frozen delta, tested on later days (the live shared sample or a new golden set), would be the next step. Proposal recorded; not started.
- Cost: US$0.15 of the US$2.00 lab budget.

## 2026-11-22 Self-consistency result (T298): no gain for five times the cost
- Run (owner approval H36): five samples of the `llm_context` prompt averaged, on the 24 frozen test questions, US$0.0871 in total. Brier 0.1961 against 0.1937 for one call: difference -0.0024 [-0.0161, +0.0110], so no measurable gain, at 5.2 times the cost (US$0.067 vs US$0.013 for 24 questions). 2 of 120 samples stopped at the output limit.
- Decision: self-consistency is not added to any live forecaster; the card stays in the eval table (small sample, wide interval). The variant and its tests stay in the code as a reproducible negative result.

## 2026-11-22 Distillation labels: first run stopped at its token cap; second run completes the sample
- Context: `lab-distill-labels` (owner approval H27) labelled 773 of 1,200 training questions (US$0.4117), then my own hard cap of 2.2M tokens stopped it: the real cost was about 2.8k tokens per question, not the 1.8k I planned for. A cap that stops a run is the guard doing its job; the estimate was wrong.
- Problem: the sample is sorted by id, so the labelled part covers only four templates (`evening_gt`, `max_gt`, `mean_gt`, most of `min_lt`). Training the student on that alone would teach it only part of the question mix. Nothing is committed as the final label file yet.
- Decision: keep the first run's probabilities (`lab/data/distill-run1-probs.json`, the logged sample hash matches), add `--start` to the command, raise the default cap to 3.6M, and label the remaining 426 rows (templates `min_lt`, `spread_gt`, `up_vs_today`) in a second run of about US$0.23. `arena lab distill-merge` then builds the final label file and refuses a label for a non-training row. Total label cost about US$0.64; the lab budget total stays under US$2.00.

## 2026-11-22 forecast-audit (owner brief): scope, labels and what is deliberately left out
- Context: the owner supplied a development brief for an open-source release that doubles as a hiring portfolio: an offline tool that compares two sets of binary forecasts and the alert decisions they trigger, including days with no on-time prediction, plus one German electricity case produced by the same engine.
- Decisions: (1) the engine is one standard-library module with a CLI wrapper under `examples/forecast-audit/`, not a package and not an `arena` subcommand, so a newcomer needs only Python 3.12; (2) the project's scoring conventions are used as defaults but verified by a test against `arena.scoring.core` rather than imported; (3) timing is labelled `declared`, `replayed` or `ledger-verified`, and the electricity case is `replayed` (the as-of time recorded in the frozen golden set), never presented as live; (4) the case uses the 46 evening questions of the two frozen golden sets with the stored GGUF margins and the base rate; the classical gradient-boosted arm is left out of v0.1 because the row-level predictions of its original backtest were never committed (a separately identified replay may add it); (5) only derived binary events and probabilities are shipped, no price series, because the SMARD page says the licensing of wholesale prices is under review; (6) costs 1:4 are illustrative and the result is descriptive, not a claim of real savings.
- Result recorded: the base rate has the better Brier (0.2337 vs 0.2499) yet both make the same 46 alert decisions (every probability is above the 0.20 cutoff): under these costs the extra model changes nothing. At a 1:1 cost ratio the model's loss is higher than always alerting.
- Not done by the agent (owner steps): outreach, volunteer pilot, GitHub About text and topics, any upstream pull request, CV and contact details.


## 2026-11-22 LLM-as-judge result (T252b): ranking only until the owner's labels exist
- Run: 100 stored rationales (20 per forecaster), Claude Haiku as judge, US$0.0364, no skips. Mean data-use score: `llm_context` 3.4, `agent_graph` 3.2, `agent` 3.1, `llm_plain` 1.85, `llm_local` 1.4; direction 4.9 to 2.35.
- Decision: report as an uncalibrated ranking with the same-family-bias caveat; no claim of agreement with humans until H29 (30 labels) provides kappa. No live change (I8).

## 2026-11-22 Ask the Arena: a chat over the published record, not a prediction service
- Context: the owner asked for a chatbot that predicts any question, for example the price of a stock on a given day. Declined: a stock is a financial instrument (investment-recommendation duties, possible licence for personal advice), an on-demand prediction breaks forecast-before-truth (I1), and a public LLM endpoint needs a server and an exposed key.
- Decision (owner choices 2026-11-22): a chat that runs free in the browser on the static site, answers only from the published forecasts, results, boards and documents, declines what is not forecast and shows the nearest published question. No new predictions, no stock or advice answers, nothing stored or sent.
- Design: a guard first; tier 0 looks up a published question (slots: date, topic, threshold) or a board; tier 1 searches the documents with BM25 and quotes the best sentences with citations; otherwise it declines. For a forecast answer the leading forecaster is chosen by difficulty: the ML model when decisive (15 points from 50%), else the forecaster with the best record on that topic (at least 20 questions), else the base rate; all locked forecasts are listed. That rule is the routing study's `ml_only` idea and is labelled a hypothesis.
- Rejected: an LLM behind a key (cost, abuse, S8), a server, embeddings in the browser (size) and a tier 2 browser model for now (T316 needs the owner's OK).
- Evaluation: `evals/golden/chat-v1.jsonl` plus lookups generated from the pack; honest limits are on the card.

## 2026-11-23 Distillation result (T247): the student keeps little of the teacher's skill; not live
- Run: the owner's Colab T4 session (release `lab-distill-r1`; labels hash, pre-registration hash and dataset hashes match the repository). 276 frozen test questions, 46 days, paired day-block intervals.
- Result: student Brier 0.2365; untuned 0.2486 (-0.0121 [-0.0156, -0.0084], excludes zero); hard-label QLoRA 0.2378 (-0.0012 [-0.0046, +0.0019], no difference); teacher Claude 0.1802 (student +0.0563 [+0.0352, +0.0766], clearly worse); base rate 0.2182 (student +0.0184 [+0.0054, +0.0321], clearly worse); `ml` 0.1663.
- Hypotheses (written before the labels existed): H-DS1 (closer to the teacher than QLoRA) holds only marginally: mean absolute difference 0.1688 against 0.1737. H-DS2 (does not beat the base rate) holds. H-DS3 (teacher not better than the base rate) is refuted: the teacher beats the base rate by -0.0379 [-0.0590, -0.0158].
- Cost: the teacher costs about US$0.53 per 1,000 questions at list price; the student costs nothing on CPU but gives up almost all of the teacher's gain on these 1,198 labelled questions. No GGUF, not a live forecaster, no change to any live prompt (I8). A larger label set or a bigger student would be a new pre-registered experiment.

## 2026-11-23 Profile README is a generated draft, not a push to the profile repository
- Context: the owner asked to present Forecast Arena properly on their GitHub profile. The profile page is the README of a separate repository (`JASHD12/JASHD12`); CLAUDE.md forbids pushes or pull requests to any other repository, and About text, topics and pinning are repository settings (S4).
- Decision: `scripts/profile_readme.py` generates `docs/profile/PROFILE_README.md` from the same sources as the main README (no hand-typed numbers); a test fails if it is stale; the owner pastes it (H42). Contact lines appear only from `recruiter_facts.json`; no personal fact (degree, city, hours) is invented.

## 2026-11-23 Ask the Arena tier 2: an opt-in in-browser model that may only reword (T316)
- Owner OK (chat, 2026-11-23). Adds the only third-party downloads of the site: WebLLM 0.2.87 (Apache-2.0) from jsDelivr, the Qwen2.5-0.5B-Instruct MLC weights (Apache-2.0, about 290 MB) from Hugging Face, runtime wasm from GitHub, all after a click and only in browsers with a WebGPU adapter.
- Safeguards: the library is fetched as text and refused unless its SHA-256 matches the pinned value; the extra hosts are allowed by a Content-Security-Policy on `ask.html` only (every other page keeps `connect-src 'self'`); the model never sees the question, only the facts of an answer already produced by lookup or documents; its wording is shown only if every number occurs in those facts and the guard passes it; declines and refusals are never reworded; nothing typed leaves the device. The privacy page says what is downloaded and that the browser caches it.
- Honest limits: the code is tested with a fake engine and a stubbed WebGPU only; it has not run against a real WebGPU browser, and the jsDelivr copy of the library was not reachable from the build environment to confirm its bytes. The tier-2 wording is not part of the golden evaluation (a 0.5B model's phrasing varies); the grounding check is the safety net, not a quality claim.

## 2026-11-23 First live morning run with the fine-tuned model and crypto (T279 measurement)
- Run `2026-11-23-morning-1` (scheduler start 07:41 UTC, 08:02 UTC end, 21 minutes; code 8df51ee; batch day 2026-11-23, 43 questions in five topics): sealed at 08:02 UTC, 88 minutes before the 09:30 UTC lock. All eight health checks passed (sealed, data contracts, nothing overdue, sources fresh, `forecaster_coverage` complete with 387 forecast-or-skip pairs, no ML skips, 0 of 80 LLM answers unparseable, ledger verify).
- `llm_local_ft` (version `qwen2.5-1.5b-qlora-r1|gguf-aecc8948|platt-0.5903-0.1730|prompt-v1-b60acd4b5b85`) wrote 15 forecasts (probabilities 0.44 to 0.57) and 28 `not_sampled` skips, no other skip reasons; the GGUF cache and download did not fail the run. Seconds per question cannot be read from the ledger (the forecasters run in one window); the whole run took 21 minutes.
- LLM tokens 199,608 (169,200 in, 30,408 out, 66 requests) against the 300,000 cap, so about 100,000 tokens of room before `agent_hybrid` is switched on.
- The first crypto day: all 10 crypto questions have base rate, persistence and `ml`; 3 have LLM forecasts, 1 the LangGraph agent. The official start file now reads 2026-11-23 (not-before date used correctly, not 2099).
- Decision: no cap or budget change. `agent_hybrid` stays off until its own launch check; one flag per day.

## 2026-11-23 The `ml`-first routing rule gets a pre-registration for fresh days (T327)
- Context: the routing study's pre-registered rule saved no paid calls and the live router was closed; a simpler `ml`-first rule looked good but was picked from a grid after the fact.
- Decision: `lab/prereg/routing-ml-only.md` fixes the rule (delta 0.15), the 30 evaluation days (2026-11-24 to 2026-12-23), the hypotheses and the decision rule before any of those days exist. The evaluation waits until 2026-12-24 (T327). No live change (I8).
- `agent_hybrid` (T279): a dry run of `morning.yml` needs an unsealed batch day, so it was scheduled for the early hours of the next batch day instead of being run against today's sealed batch; the flag stays off until that measurement is clean.

## 2026-11-23 A second LLM judge is an LLM-against-LLM check, never a substitute for the owner's labels (T328)
- Context: the owner asked the agent to label the 30 judge items. Refused: the labels are meant to be human, so an agent's ratings would be another language model's, and calling the result human agreement would be a fabricated number (I5).
- Decision: (1) readable labelling cards (`lab/judge/label-cards.md`) make the owner's 30 labels faster; (2) with the owner's yes (chat, 2026-11-23) one small paid run lets Claude Sonnet 5.5 grade the same 30 items; `arena lab judge-compare` reports weighted kappa and exact match between the two models, labelled "not agreement with a human". Same-family bias is a stated limit. Cost estimate about US$0.22 at the list price read on 2026-11-23, hard token cap 100,000, budget after the run about US$1.2 of 2.00. H29 stays open.

## 2026-11-23 Agent ratings of the 30 judge items: a labelled third rater, not the owner's labels (T328)
- Context: the owner asked the agent to fill the 30 labels with assumptions because they would not label them. Filling the human-label file with invented numbers was refused (I5); instead the agent read each of the 30 cards and rated them on the three scales, saved as `lab/judge/ratings-agent.json`.
- Result (`evals/results/lab-judge-agent.json`, card `docs/lab/judge-agent.md`): weighted kappa between the Haiku judge and the agent rater 0.771 (data_use), 0.767 (direction), 0.723 (hedging); exact match 43% / 67% / 67%, on 30 rationales. Labelled "not a human" everywhere; limits: same model family, not blind to the judge, small sample.
- The agent's ratings are never written into the owner-label path (`labels.csv` for `judge-eval`); H29 stays open and the judge on the Lab page stays "uncalibrated against humans".

## 2026-11-23 Second LLM judge result (T328): the two models agree with each other, which is not calibration
- Run (owner approval, chat 2026-11-23): Claude Sonnet 5.5 graded the 30 labelled items, `lab-judge` run 45258529928, US$0.134 (estimate was US$0.22), 30 of 30 scored, no skips. Lab budget US$1.09 of 2.00.
- Agreement between the Haiku judge and the Sonnet judge: weighted kappa 0.80 / 0.75 / 0.76 and exact match 50% / 50% / 77% (data_use / direction / hedging). Between Sonnet and the agent's own ratings the kappas are higher (0.85 / 0.81 / 0.81, computed once, not published as a separate card). Three LLM raters broadly agree, which only says the rubric is reproducible across models; it does not say they agree with a human. H29 stays open.
