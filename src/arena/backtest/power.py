"""Power backtest: base_rate and persistence vs `ml`, walk-forward with periodic retraining."""

from __future__ import annotations

from datetime import date, timedelta

from arena.backtest.harness import BacktestResult, walk_forward
from arena.domains.power import PowerDomain
from arena.forecasters.baselines import BaseRate, Persistence
from arena.forecasters.ml import MLForecaster
from arena.forecasters.ml_power import PowerModel, train

NOTES = (
    "Features: calendar (weekday, season, German national holidays) and the last 28 days "
    "of daily price statistics from the as-of context only.",
    "Not used: load/generation actuals, weather forecasts and official day-ahead forecasts "
    "(no as-of history of forecasts is available; adding them would make a backtest "
    "'optimistic').",
    "Models are retrained on an expanding window every `retrain_days`, each time with "
    "targets up to the day before the batch; calibration uses out-of-fold predictions.",
    "Baselines learn only from outcomes known by each morning of the walk-forward "
    "(after a warm-up period whose forecasts are not scored).",
)


def run(
    domain: PowerDomain,
    first: date,
    last: date,
    *,
    run_id: str,
    retrain_days: int = 91,
    warmup_days: int = 120,
    folds: int = 2,
    max_iter: int = 100,
) -> BacktestResult:
    """Walk-forward from `first` to `last` (scored), with a warm-up before `first`."""
    state: dict[str, PowerModel] = {}

    def refresh(domain_name: str, day: date) -> PowerModel | None:
        if domain_name != "power":
            return None
        cur = state.get("m")
        if cur is None or (day - cur.train_end).days > retrain_days:
            state["m"] = train(domain, day - timedelta(days=1), folds=folds, max_iter=max_iter)
            return state["m"]
        return None

    return walk_forward(
        run_id,
        domain,
        lambda h: [BaseRate(h), Persistence(h), MLForecaster({}, refresh)],
        first - timedelta(days=warmup_days),
        last,
        warmup=warmup_days,
    )
