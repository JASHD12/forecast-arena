# DECISIONS.md - design decisions

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
Decision: `requirements-lock.txt` with exact `==` pins of the packages already installed in
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
with SQLAlchemy and Alembic) is pinned in `requirements-tracking.txt`, installed by the
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
Decision: Evidently 0.7.23 (pinned with pandas 2.3.3 in `requirements-tracking.txt`; it
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
