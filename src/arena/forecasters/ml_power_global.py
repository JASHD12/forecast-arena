"""Global LightGBM quantile model for the power `ml` forecaster (T275, weekly challenger).

The champion (`power-gbq`) and the first LightGBM challenger (`power-lgbq`) fit one set of
quantile regressors per daily statistic. A *global* model (the pattern used in demand
forecasting: one model across many related series) fits ONE LightGBM per quantile level on
the rows of all five statistics stacked, with the statistic as a one-hot feature and each
target standardised by its training mean and standard deviation. It shares data across the
statistics and trains five times fewer models. Features, targets, calibration and question
logic are those of `ml_power`; the family name `power-glgbq` keeps its artefacts apart. It
enters the live record only if the weekly job promotes it under the written rule (not worse
than the current model on the same recent questions).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from arena.domains.power import PowerDomain
from arena.forecasters.ml_power import QUANTILES, STATS, PowerModel, train
from arena.forecasters.ml_power_lgbm import DEFAULT_PARAMS, _regressor

FAMILY = "power-glgbq"


@dataclass
class StatView:
    """One level of the global model, seen as a regressor of a single statistic."""

    model: Any
    stat_index: int
    n_stats: int
    mean: float
    std: float

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Predicted quantile of the statistic, on its own scale."""
        onehot = np.zeros((len(x), self.n_stats))
        onehot[:, self.stat_index] = 1.0
        z = self.model.predict(np.hstack([np.asarray(x, float), onehot]))
        return np.asarray(z) * self.std + self.mean


def fit_global_quantiles(
    x: np.ndarray, ys: dict[str, np.ndarray], params: dict[str, Any] | None = None, seed: int = 0
) -> dict[str, list[StatView]]:
    """One LightGBM per level on all statistics stacked; returns {stat: [view per level]}."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    stats = list(STATS)
    n = len(stats)
    stacked, targets = [], []
    scale: dict[str, tuple[float, float]] = {}
    for i, s in enumerate(stats):
        mu, sd = float(np.mean(ys[s])), float(np.std(ys[s])) or 1.0
        scale[s] = (mu, sd)
        onehot = np.zeros((len(x), n))
        onehot[:, i] = 1.0
        stacked.append(np.hstack([x, onehot]))
        targets.append((ys[s] - mu) / sd)
    big_x, big_y = np.vstack(stacked), np.concatenate(targets)
    models = [_regressor(q, p, seed).fit(big_x, big_y) for q in QUANTILES]
    return {s: [StatView(m, i, n, *scale[s]) for m in models] for i, s in enumerate(stats)}


def train_global(
    domain: PowerDomain, train_end: date, *, folds: int = 2, seed: int = 0
) -> PowerModel:
    """Fit and calibrate exactly like the champion, with the global quantile model."""
    return train(
        domain,
        train_end,
        folds=folds,
        multi_fitter=lambda x, ys: fit_global_quantiles(x, ys, None, seed),
        family=FAMILY,
        params=dict(DEFAULT_PARAMS),
    )
