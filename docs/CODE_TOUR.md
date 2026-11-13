# Code tour: five files worth five minutes

If you read only five files, read these. Each one carries one of the guarantees the
project is built on. Line counts are approximate; everything is typed and tested.

## 1. The append-only ledger: `src/arena/ledger/store.py` and `verify.py`

`Ledger.append` is the only way a record enters the public record. It refuses files of a
sealed day, refuses records of the wrong kind or with a duplicate id, writes canonical
JSON, and replaces the file atomically (temporary file, validate, rename), so a crash
never leaves half a line. `verify.verify` recomputes every batch seal and the daily hash
chain and checks that every forecast was created before its question's lock. Run it on
the public branch with `arena ledger verify --git`.

**Why it matters:** forecasts are only worth something if nobody, including the author,
can change them after the answer is known.

## 2. No look-ahead: `src/arena/domains/base.py` (`AsOfStore.series`)

Every observation carries the time it became public. `series(key, asof)` returns only
what was available at `asof`, and for a value that was later revised, the version that
was public then. Forecasters never touch a data source directly; they get a context built
from this gateway. The same code path replays the past in backtests, which is why the
backtest numbers mean something.

## 3. A classical forecaster: `src/arena/forecasters/ml_power.py`

Features from the past 28 days of prices, gradient-boosted quantile regression for each
daily statistic, the quantiles interpolated into a distribution (`cdf_at`), the
probability that the statistic exceeds the question's threshold read off it, then
calibrated. One model answers every threshold consistently. Challengers (LightGBM tuned
with Optuna, a PyTorch network, statistical and pretrained time-series models) plug into
the same interface and are promoted only by the written rule in `ops/weekly.py`.

## 4. The agent: `src/arena/agent/forecaster.py` and `tools.py`

`AgentForecaster._loop` is a plain tool-calling loop over our own `LLMClient`: call the
model, run requested tools within the limits, repeat, then parse a strict JSON answer
with one repair. The harness, not the prompt, enforces the limits (number of calls, time,
the daily token budget through `llm/budget.py`). Tool output is treated as data. Every
failure becomes a recorded skip with a reason, never a default probability. The LangGraph
version of the same agent is in `agent/graph.py`.

## 5. Scoring and statistics: `src/arena/scoring/core.py` and `stats.py`

Brier and log scores on clipped probabilities, skill against the base rate, paired
comparisons only on questions both forecasters answered, day-block bootstrap intervals
(questions on the same day are correlated), Diebold-Mariano tests in the backtests, and a
power calculation of how many days a difference needs. A board says "too early to tell"
until the data can decide.

## Then, if you have more time

- `src/arena/ops/jobs.py`: the scheduled jobs (evening, morning, players, resolve), each
  idempotent and lock-aware; `ops/schedule.py` is the gate that lets late-starting
  scheduled runs do the work exactly once.
- `tests/e2e/test_e2e.py`: five simulated days through the real job code, run on every
  push, then run again to prove that nothing changes.
- `docs/SPEC.md` and `docs/project/DECISIONS.md`: what was built, and why.
