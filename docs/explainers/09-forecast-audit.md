# 09 - forecast-audit: how it works, why it is built this way, what was left out

A small offline tool, `examples/forecast-audit/`, and one site page (`audit.html`) generated from
its output. Design record: `docs/project/DECISIONS.md` (2026-11-22, forecast-audit).

## What it does

Two CSV files in (`cases.csv`: the question calendar and outcomes; `predictions.csv`: one row per
model and case), a report out (`report.json`, `cases-audited.csv`, `report.html`). Python 3.12,
standard library only. It answers one question: *if I send alerts from my model's probabilities,
do the decisions improve over a baseline, including the days it misses?*

Three views from the same classified rows:

1. **Timeliness and coverage.** A prediction is on time only if `issued_at` is strictly before
   `lock_at`. Late, skipped (with a reason) and absent are counted apart. An unknown roster means
   "coverage unknown", never 100%.
2. **Probability quality** on the identical set of on-time resolved cases (raw and clipped Brier),
   so models are never compared on different questions.
3. **Decision performance.** Alert if `p >= false_alert_cost / (false_alert_cost + miss_cost)`
   (ties alert). Missing or late forecasts fall back by a declared rule. Always-alert and
   never-alert are shown; cost ratios 1:1 and 1:9 are sensitivity checks.

## The German electricity case

46 evening-price questions (29 YES, 17 NO) replayed from frozen records. The base rate has the
better Brier (0.2337 against 0.2499) and both models raise the same 46 alerts at a 20% threshold,
17 of them false, so the extra model changed no decision. Timing is labelled **replayed**: the
as-of stamp comes from the frozen record, not a live ledger time.

## Why it is built this way

- **Standard library only** so a newcomer runs it with no install, and CI proves it on a bare Python.
- **Invalid input is a hard error** (exit 2, no partial output): a quiet fix would change a score.
- **Generated sentences.** The site headline is produced from `report.json` (I5).
- **A second calculation.** `audit.sql` repeats the counts and losses in DuckDB; a test checks agreement.
- **Only derived data is shipped** (binary outcomes and probabilities, no hourly prices) because the
  source's licence terms are under review.

## What was rejected

- A package and a CLI inside `arena`: it would force installation and tie the tool to this repository.
- Adding the classical ML arm: its row-level backtest predictions were never committed.
- A significance claim on 46 cases: the day-block interval needs at least 30 days; below that the
  report says "not estimated".
- Money values: costs are illustrative units.

## Honest limits

A replay is not a live result; 46 cases is small; the costs are assumed; there is no independent
user feedback yet (the pilot in `docs/pilot/forecast-audit-pilot.md` is the owner's step).

## Ten questions an interviewer may ask

1. Why can a worse-Brier model give the same decisions? Alerts depend only on which side of the
   cutoff a probability falls; here every probability of both models is above 0.20.
2. Why compare on identical cases? Otherwise a model that skips hard days looks better.
3. Why is "on time" strictly before the lock? A forecast at the lock instant could see the answer.
4. What does the fallback option do? It decides what to do on days with no usable forecast; the default is no alert, and the other options are reported as sensitivity.
5. Why clip probabilities? A 0 or 1 that is wrong has unbounded log score and a hard Brier hit; the arena clips to [0.01, 0.99] and the tool reports both.
6. Why no confidence interval here? Resampling needs enough independent days; below 30 it says so.
7. How do you know the numbers are right? Hand-checked four-case table, conformance tests against `arena.scoring.core`, and the DuckDB cross-check.
8. Why a replay label? Honesty about timing: only a ledger-verified timestamp proves forecast-before-truth.
9. What would you do with real money costs? Replace the illustrative units with the user's own, which are CLI arguments.
10. What is the next step? A role-specific extension chosen from pilot feedback (T325), not guessed.
