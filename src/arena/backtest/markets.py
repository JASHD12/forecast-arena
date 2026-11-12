"""Markets backtest: base_rate and persistence vs `ml` (EWMA volatility, direction 0.5)."""

from __future__ import annotations

from datetime import date, timedelta

from arena.backtest.harness import BacktestResult, walk_forward
from arena.domains.markets import MarketsDomain
from arena.forecasters.baselines import BaseRate, Persistence
from arena.forecasters.ml import MLForecaster
from arena.forecasters.ml_markets import MarketsModel

NOTES = (
    "ml = EWMA (lambda 0.94) volatility of per-weekday log returns, Student t with 5 degrees "
    "of freedom, scaled by the weekdays between fixings; `up` is fixed at 0.5.",
    "The model has no fitted parameters, so there is no training window; inputs are the "
    "fixings known before the batch day's fixing (as-of context).",
    "Baselines learn only from outcomes known by each morning of the walk-forward "
    "(after a warm-up period whose forecasts are not scored).",
)


def run(
    domain: MarketsDomain, first: date, last: date, *, run_id: str, warmup_days: int = 180
) -> BacktestResult:
    """Walk-forward from `first` to `last` (scored), with a warm-up before `first`."""
    return walk_forward(
        run_id,
        domain,
        lambda h: [BaseRate(h), Persistence(h), MLForecaster({"markets": MarketsModel()})],
        first - timedelta(days=warmup_days),
        last,
        warmup=warmup_days,
    )
