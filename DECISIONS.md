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


Ideas outside the specification. The agent lists them here and does not build them.

(none yet)
