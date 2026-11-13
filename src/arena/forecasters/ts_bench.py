"""Time-series benchmarks for power (T114): statistical models and a pretrained
foundation model, each turned into P(YES) through its predictive quantiles.

All three are *local* models: at forecast time they look only at the as-of context (the
daily statistics of the last 28 known days, `PowerDomain.context`) and forecast the
statistic of the target day `h` steps ahead (normally h = 1: the latest known day is B,
the target is D = B + 1). Nothing is trained on other days, so there is no training
cut-off to leak through, and nothing is calibrated afterwards: these are benchmarks for
the `ml` champion, reported as measured.

- `ets`: additive-error exponential smoothing with additive weekly seasonality
  (`statsmodels` `ETSModel`, error="add", seasonal="add", period 7), Gaussian predictive.
- `sarimax`: SARIMA(1,0,0)(1,0,0)[7] with a constant (`statsmodels` `SARIMAX`),
  Gaussian predictive.
- `chronos`: Chronos-Bolt tiny (Amazon, Apache-2.0, 9M parameters), zero-shot on the
  same 28 values, nine predicted quantiles 0.1..0.9; weights pinned to a revision.
"""

from __future__ import annotations

import hashlib
import math
import os
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from statistics import NormalDist
from typing import Any

import numpy as np

from arena.models import Question

#: Quantile levels at which Gaussian predictives are evaluated (same as Chronos-Bolt).
LEVELS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
MIN_POINTS = 14
CHRONOS_MODEL = "amazon/chronos-bolt-tiny"
CHRONOS_REVISION = "a0e552de83495b5c28c14c71c374f3e33280b340"
REVISION = 1


def cdf_from_quantiles(levels: Sequence[float], values: Sequence[float], t: float) -> float:
    """P(X <= t) by linear interpolation between predicted quantiles; beyond the outer
    quantiles the tail mass is halved towards 0 and 1 (as `ml_power.cdf_at`)."""
    v = np.sort(np.asarray(values, float))
    qs = np.asarray(levels, float)
    if t < v[0]:
        return float(qs[0] / 2)
    if t >= v[-1]:
        return float(1 - (1 - qs[-1]) / 2)
    return float(np.interp(t, v, qs))


def gaussian_cdf(mean: float, var: float, t: float) -> float:
    """P(X <= t) for X ~ N(mean, var); a point mass when the variance is zero."""
    if not math.isfinite(mean) or not math.isfinite(var):
        raise ValueError("non-finite predictive")
    if var <= 0:
        return 1.0 if t >= mean else 0.0
    return NormalDist(mean, math.sqrt(var)).cdf(t)


Predictor = Callable[[tuple[float, ...], int], Callable[[float], float]]


def _ets(series: tuple[float, ...], h: int) -> Callable[[float], float]:
    import pandas as pd
    from statsmodels.tsa.exponential_smoothing.ets import ETSModel

    y = pd.Series(np.asarray(series, float))  # ETS prediction needs an indexed series
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = ETSModel(y, error="add", trend=None, seasonal="add", seasonal_periods=7).fit(
            disp=False
        )
        pred = res.get_prediction(start=len(y) + h - 1, end=len(y) + h - 1)
        mean = float(np.asarray(pred.predicted_mean)[-1])
        var = float(np.asarray(pred.var_pred_mean)[-1])
    return lambda t: gaussian_cdf(mean, var, t)


def _sarimax(series: tuple[float, ...], h: int) -> Callable[[float], float]:
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    y = np.asarray(series, float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = SARIMAX(y, order=(1, 0, 0), seasonal_order=(1, 0, 0, 7), trend="c").fit(disp=False)
        fc = res.get_forecast(h)
        mean = float(np.asarray(fc.predicted_mean)[-1])
        var = float(np.asarray(fc.var_pred_mean)[-1])
    return lambda t: gaussian_cdf(mean, var, t)


@lru_cache(maxsize=1)
def chronos_pipeline() -> Any:
    """Load Chronos-Bolt tiny on CPU (downloaded once into the Hugging Face cache)."""
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")  # plain HTTPS download
    import torch
    from chronos import BaseChronosPipeline

    torch.manual_seed(0)
    return BaseChronosPipeline.from_pretrained(
        CHRONOS_MODEL, revision=CHRONOS_REVISION, device_map="cpu", torch_dtype=torch.float32
    )


def _chronos(series: tuple[float, ...], h: int) -> Callable[[float], float]:
    import torch

    pipe = chronos_pipeline()
    with torch.no_grad():
        q, _ = pipe.predict_quantiles(
            torch.tensor(series, dtype=torch.float32),
            prediction_length=h,
            quantile_levels=list(LEVELS),
        )
    values = [float(v) for v in q[0, h - 1, :]]
    return lambda t: cdf_from_quantiles(LEVELS, values, t)


PREDICTORS: dict[str, Predictor] = {"ets": _ets, "sarimax": _sarimax, "chronos": _chronos}
FAMILIES = {"ets": "power-ets", "sarimax": "power-sarimax", "chronos": "power-chronos-bolt-tiny"}


@dataclass
class SeriesBenchmark:
    """A local time-series model per question; fits the `MLForecaster` model protocol."""

    method: str
    train_end: date = date.min  # nothing is trained; kept for the backtest refresher
    _cache: dict[tuple[str, tuple[float, ...], int], Callable[[float], float]] = field(
        default_factory=dict, repr=False
    )

    def __post_init__(self) -> None:
        if self.method not in PREDICTORS:
            raise ValueError(f"unknown method {self.method!r}")

    @property
    def version(self) -> str:
        """Family and revision (no artefact: the model is refitted for each question)."""
        return f"{FAMILIES[self.method]}-r{REVISION}"

    def model_hash(self) -> str:
        """Short hash of the version (and, for Chronos, the pinned weights revision)."""
        blob = f"{self.version}|{CHRONOS_REVISION if self.method == 'chronos' else ''}"
        return hashlib.sha256(blob.encode()).hexdigest()[:12]

    def cdf(self, stat: str, ctx: dict[str, Any], target: date) -> Callable[[float], float]:
        """Predictive CDF of `stat` on `target` from the context's daily rows."""
        rows = ctx["daily"]
        series = tuple(float(r[stat]) for r in rows)
        if len(series) < MIN_POINTS:
            raise ValueError(f"only {len(series)} known days (need {MIN_POINTS})")
        h = (target - date.fromisoformat(rows[-1]["day"])).days
        if h < 1:
            raise ValueError(f"target {target} is not after the latest known day")
        key = (stat, series, h)
        if key not in self._cache:
            if len(self._cache) > 512:
                self._cache.clear()
            self._cache[key] = PREDICTORS[self.method](series, h)
        return self._cache[key]

    def probability(self, q: Question, ctx: dict[str, Any]) -> float:
        """P(YES) for a power question."""
        stat = str(q.params["stat"])
        thr = float(q.params["reference_mean"]) if q.template == "up_vs_today" else q.threshold
        if thr is None:
            raise ValueError("question has no threshold")
        f = self.cdf(stat, ctx, q.target_date)(thr)
        return f if q.comparator == "lt" else 1 - f
