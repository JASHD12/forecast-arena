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

## Proposals for the human

Ideas outside the specification. The agent lists them here and does not build them.

- **Template-level base rate for attention.** SPEC 8.1 defines `base_rate` per template
  and entity. For attention the entity is an article that rarely repeats, so `base_rate`
  is always 0.5 there. A template-level variant (same template, any article) would be a
  more informative baseline. Needs a human decision because it changes a SPEC 8 rule.
