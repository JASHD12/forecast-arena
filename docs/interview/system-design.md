# System design walkthrough

Draw this left to right. Say the guarantee each box gives, not only what it is.

```
 public data          GitHub Actions (code from the `stable` branch)         outputs
 ───────────          ───────────────────────────────────────────────        ───────
 SMARD prices  ─┐     evening  18:00  questions for tomorrow (v2)       ┌─▶ ledger branch
 DWD weather   ─┼──▶  morning  05:30  every forecaster answers, seal ───┤   (append-only
 Wikimedia     ─┤     players  09:00  public players' answers           │    JSONL + hash
 ECB rates     ─┘     ── 09:30 UTC lock: nothing more for the batch ──  │    chain)
                      resolve  4x/day answers, scores, day seals   ─────┤
                      weekly   Sun    retrain, champion/challenger ─────┘─▶ GitHub Pages
                                                                            (static site,
                                                                             JSON API)
```

## 1. Questions (domains)

- Each topic is a `Domain` with `generate_questions(batch, asof)`, `context(q, asof)` and
  `resolve(q)` (`src/arena/domains/`). Templates are fixed in code, with thresholds taken
  from the recent past (for example the median of the last 28 days), so a question is
  neither trivially YES nor trivially NO. A degeneracy rule drops templates whose recent
  YES rate is extreme.
- Every question has a `lock_time` (09:30 UTC, before the noon electricity auction) and a
  `resolve_after` time. Its id ends in the template version; a changed template is a new
  version, and old questions keep theirs (publishing the evening before is version 2).

## 2. No leakage: the as-of gateway

- Every value is stored with the time it became public (`AsOfStore`). A forecaster only
  ever receives `context(q, asof)`, which filters on that time. This is what makes
  backtests honest: replaying a past day sees only what was public then.

## 3. Forecasters (same interface for all)

- `forecast(question, context, asof) -> Forecast | Skip`.
- Baselines: base rate (Laplace-smoothed YES share of past instances) and persistence.
- ML: gradient-boosted quantile regression of the daily price statistics, turned into
  P(statistic > threshold) and calibrated. Retrained weekly; challengers (LightGBM tuned
  with Optuna, a PyTorch network, time-series models) are promoted only by a written rule.
- LLMs (Claude Haiku via the Anthropic API): plain, with data, a tool-calling agent, a
  LangGraph agent; plus a local open-weights model through llama.cpp. All return strict
  JSON, get one repair attempt, and are wrapped by a guard that enforces a daily token
  cap. Failures become recorded **skips** with a reason, never a default 0.5.

## 4. The ledger (integrity)

- An orphan git branch of JSONL files, one record per line, canonical JSON. Writes go to
  a temp file, are validated, then atomically renamed; ids are unique per family.
- **Batch seal** after the morning run: hashes of the batch's question and forecast files.
  **Day seal** after each UTC day: hashes of every file of that day plus the previous
  day's chain hash. `arena ledger verify` recomputes everything and checks every forecast
  was created before its lock; `--git` also checks commit times against the lock.
- Append-only: corrections are new records that say what they correct.

## 5. Resolution and scoring

- Resolve jobs fetch the official value, store the evidence (values used, source hash),
  and write a resolution or a void (missing data after a grace period).
- Brier and log score; skill against the base rate; reliability diagrams; day-block
  bootstrap intervals (questions on the same day are correlated); Diebold-Mariano in the
  backtests. Under 30 official days the site says "too early to tell".
- The official record starts only after five clean days in a row and not before a date
  set in advance, so early version churn never counts.

## 6. Operations

- `main` must pass `make check` (lint, types, unit tests, offline end-to-end run). A
  `promote` workflow moves green commits to `stable`; scheduled jobs run `stable`.
- Every job is idempotent and scheduled twice; a shared concurrency group means one
  ledger writer at a time. Health checks after each job open or close an `incident`
  issue. Cost: hard daily token cap; LLM calls only inside Actions; tests use a fake LLM.

## 7. Trade-offs to volunteer

- **Git as a database**: free, public, tamper-evident history; but slow for queries, so
  analytics export Parquet and query with DuckDB.
- **Static site**: no server to secure or pay for; anything dynamic is precomputed.
- **Daily cadence**: a slow feedback loop, so meaningful live results take months. The
  site shows intervals and a power analysis instead of pretending otherwise.
- **Small samples for LLMs**: the LLMs answer a daily sample to stay under the budget,
  so their intervals are wider than the baselines'.
