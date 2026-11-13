"""LightGBM challenger for the power `ml` forecaster (T112, owner-approved roadmap).

Same features, targets, calibration and question logic as `ml_power` (the champion family
`power-gbq`); only the quantile regressors differ: one LightGBM model per quantile level
(objective "quantile", `alpha` = level). Hyperparameters are tuned with Optuna (TPE
sampler, fixed seed) on a time-series split of the training rows: each fold trains on
targets before the fold minus a gap and validates on the fold, never shuffled. The loss
is the mean pinball loss at the 0.1, 0.5 and 0.9 levels for the daily mean price.

The challenger only enters the live record if the weekly job promotes it (it must score
at least as well as the champion on the same recent questions; `arena.ops.weekly`).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np

from arena.domains.power import PowerDomain
from arena.forecasters.ml_power import CONTEXT_DAYS, QUANTILES, PowerModel, train, training_rows

FAMILY = "power-lgbq"
TUNE_LEVELS = (0.1, 0.5, 0.9)
DEFAULT_PARAMS: dict[str, Any] = {
    "num_leaves": 15,
    "learning_rate": 0.05,
    "n_estimators": 150,
    "min_child_samples": 20,
    "reg_lambda": 1.0,
}


def _regressor(alpha: float, params: dict[str, Any], seed: int) -> Any:
    from lightgbm import LGBMRegressor

    return LGBMRegressor(
        objective="quantile",
        alpha=alpha,
        random_state=seed,
        deterministic=True,
        force_row_wise=True,
        n_jobs=1,
        verbose=-1,
        **params,
    )


def fit_quantiles_lgbm(
    x: np.ndarray, y: np.ndarray, params: dict[str, Any] | None = None, seed: int = 0
) -> list[Any]:
    """One LightGBM quantile regressor per level in QUANTILES."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    return [_regressor(q, p, seed).fit(x, y) for q in QUANTILES]


def pinball_loss(y: np.ndarray, pred: np.ndarray, tau: float) -> float:
    """Mean pinball (quantile) loss."""
    d = y - pred
    return float(np.mean(np.maximum(tau * d, (tau - 1) * d)))


def tune_lgbm(
    x: np.ndarray,
    y: np.ndarray,
    targets: list[date],
    *,
    n_trials: int = 20,
    folds: int = 2,
    fold_days: int = 60,
    gap_days: int = 7,
    seed: int = 0,
) -> dict[str, Any]:
    """Best hyperparameters by mean pinball loss on time-series folds (DEFAULT_PARAMS when
    the history is too short to tune)."""
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    t = np.asarray(targets)
    last = max(targets)
    splits = []
    for k in range(folds, 0, -1):
        f_start = last - timedelta(days=k * fold_days) + timedelta(days=1)
        f_end = f_start + timedelta(days=fold_days - 1)
        tr = t < f_start - timedelta(days=gap_days)
        te = (t >= f_start) & (t <= f_end)
        if tr.sum() >= 100 and te.sum() >= 10:
            splits.append((tr, te))
    if not splits:
        return dict(DEFAULT_PARAMS)

    def objective(trial: Any) -> float:
        p = {
            "num_leaves": trial.suggest_int("num_leaves", 7, 63),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 50, 400),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 60),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        }
        losses = []
        for tr, te in splits:
            for tau in TUNE_LEVELS:
                m = _regressor(tau, p, seed).fit(x[tr], y[tr])
                losses.append(pinball_loss(y[te], m.predict(x[te]), tau))
        return float(np.mean(losses))

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials)
    return dict(study.best_params)


def train_lgbm(
    domain: PowerDomain,
    train_end: date,
    *,
    n_trials: int = 20,
    folds: int = 2,
    seed: int = 0,
) -> PowerModel:
    """Tune on rows up to `train_end`, then fit and calibrate exactly like the champion."""
    daily = {d: v for d, v in domain.all_days().items() if d <= train_end}
    if not daily:
        raise ValueError("no price history")
    start = min(daily) + timedelta(days=CONTEXT_DAYS + 1)
    x, ys, targets = training_rows(daily, start, train_end)
    if len(targets) < 50:
        raise ValueError("too little history to train the LightGBM challenger")
    params = tune_lgbm(x, ys["mean"], targets, n_trials=n_trials, seed=seed)
    return train(
        domain,
        train_end,
        folds=folds,
        fitter=lambda xx, yy: fit_quantiles_lgbm(xx, yy, params, seed),
        family=FAMILY,
        params=params,
    )
