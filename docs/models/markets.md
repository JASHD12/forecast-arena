# Model card: `ml` for markets (markets-ewma-t5-r1)

**What it predicts.** For EUR/USD and EUR/JPY ECB reference rates: the probability that the
absolute log change from today's fixing to the next one exceeds the question's threshold,
from an EWMA (lambda 0.94) volatility estimate of per-weekday log returns and a Student t
distribution with 5 degrees of freedom, scaled by the weekdays between the two fixings.

**Direction.** The `up` template is answered with 0.5. A direction model would only be used
if a backtest showed skill with an interval excluding zero; none was built, so the markets
domain stays a clean null test of hypothesis H3.

**Inputs.** Only the fixings published before the batch day's fixing (as-of context).

**Known limits.** No fitted parameters; lambda and the degrees of freedom are textbook
choices fixed before any live resolution, not tuned on the record.

## Backtest (run `markets-2024-11-01-2026-10-31-20261112T1423`)

**BACKTEST** (not part of the live record).

Batches 2024-11-01 to 2026-10-30 (509 batch days).

| Forecaster | n | Brier | 95% interval | Log score |
|---|---|---|---|---|
| base_rate | 2036 | 0.2516 | [0.2490, 0.2541] | 0.6963 |
| persistence | 2036 | 0.2516 | [0.2490, 0.2541] | 0.6963 |
| ml | 2036 | 0.2502 | [0.2471, 0.2531] | 0.6937 |

Paired Brier differences (negative = first is better), day-block bootstrap, 2000 replicates, fixed seed:

| Comparison | Difference | 95% interval | Supported? |
|---|---|---|---|
| ml - base_rate | -0.0013 | [-0.0050, +0.0024] | no (interval includes zero) |
| ml - persistence | -0.0013 | [-0.0050, +0.0024] | no (interval includes zero) |
| persistence - base_rate | +0.0000 | [+0.0000, +0.0000] | no (interval includes zero) |

Notes:

- ml = EWMA (lambda 0.94) volatility of per-weekday log returns, Student t with 5 degrees of freedom, scaled by the weekdays between fixings; `up` is fixed at 0.5.
- The model has no fitted parameters, so there is no training window; inputs are the fixings known before the batch day's fixing (as-of context).
- Baselines learn only from outcomes known by each morning of the walk-forward (after a warm-up period whose forecasts are not scored).
