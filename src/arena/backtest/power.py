"""Power backtest: base_rate and persistence vs `ml`, walk-forward with periodic retraining."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, timedelta
from typing import Any

from arena.backtest.harness import BacktestResult, walk_forward
from arena.domains.power import PowerDomain
from arena.forecasters.baselines import BaseRate, Persistence
from arena.forecasters.ml import MLForecaster
from arena.forecasters.ml_power import PowerModel, train

#: Challenger name -> forecaster id in the backtest report.
CHALLENGER_IDS = {
    "lgbm": "ml_lgbm",
    "mlp": "ml_mlp",
    "ets": "ts_ets",
    "sarimax": "ts_sarimax",
    "chronos": "ts_chronos",
}

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
    challengers: Sequence[str] = (),
    lgbm_trials: int = 20,
) -> BacktestResult:
    """Walk-forward from `first` to `last` (scored), with a warm-up before `first`.

    `challengers` adds challenger model families as extra forecasters on the same
    questions: "lgbm" (LightGBM + Optuna, forecaster id `ml_lgbm`), "mlp" (PyTorch
    quantile network, `ml_mlp`), and the local time-series benchmarks "ets", "sarimax"
    and "chronos" (`ts_*`, see `forecasters/ts_bench.py`; no training)."""
    state: dict[str, PowerModel] = {}

    def refresher(key: str, fit: Callable[[date], PowerModel]) -> Callable[[str, date], Any]:
        def refresh(domain_name: str, day: date) -> PowerModel | None:
            if domain_name != "power":
                return None
            cur = state.get(key)
            if cur is None or (day - cur.train_end).days > retrain_days:
                state[key] = fit(day - timedelta(days=1))
                return state[key]
            return None

        return refresh

    def forecasters(h: Any) -> list[Any]:
        out: list[Any] = [
            BaseRate(h),
            Persistence(h),
            MLForecaster(
                {}, refresher("ml", lambda c: train(domain, c, folds=folds, max_iter=max_iter))
            ),
        ]
        if "lgbm" in challengers:
            from arena.forecasters.ml_power_lgbm import train_lgbm

            f = MLForecaster(
                {},
                refresher(
                    "lgbm", lambda c: train_lgbm(domain, c, n_trials=lgbm_trials, folds=folds)
                ),
            )
            f.forecaster_id = "ml_lgbm"
            out.append(f)
        if "mlp" in challengers:
            from arena.forecasters.ml_power_torch import train_torch

            g = MLForecaster({}, refresher("mlp", lambda c: train_torch(domain, c, folds=folds)))
            g.forecaster_id = "ml_mlp"
            out.append(g)
        for method in ("ets", "sarimax", "chronos"):
            if method in challengers:
                from arena.forecasters.ts_bench import SeriesBenchmark

                b = MLForecaster({"power": SeriesBenchmark(method)})
                b.forecaster_id = CHALLENGER_IDS[method]
                out.append(b)
        return out

    return walk_forward(
        run_id,
        domain,
        forecasters,
        first - timedelta(days=warmup_days),
        last,
        warmup=warmup_days,
    )
