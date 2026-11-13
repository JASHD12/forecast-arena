"""`ml` for the power domain (SPEC 8.3): quantile gradient boosting + calibration.

For each daily statistic (mean, max, min, spread, evening) a set of quantile regressors
predicts the distribution of tomorrow's value. P(statistic > T) is read off the
interpolated predicted CDF and then calibrated with a logistic (Platt) map fitted on
out-of-fold predictions for the real questions of earlier batches (expanding windows with
a gap, never shuffled).

Features come only from the forecaster context (`PowerDomain.context`: the last 28 known
days of daily statistics) plus the calendar of the target day, so training and live
forecasting see exactly the same inputs. Not used (stated on the model card): load and
generation actuals, weather forecasts and official day-ahead forecasts (no as-of history
available yet).
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression

from arena.calendar_de import is_holiday
from arena.domains.power import PowerDomain, day_stats
from arena.models import Question, Resolution

STATS = ("mean", "max", "min", "spread", "evening")
QUANTILES = (0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98)
CONTEXT_DAYS = 28
MORNING = time(5, 30)
FAR = datetime.max.replace(tzinfo=UTC)
MODEL_FAMILY = "power-gbq"
MODEL_REVISION = 1


def features(daily: Sequence[dict[str, Any]], target: date) -> list[float]:
    """Feature vector from context-style daily rows (oldest first) for target day D."""
    if not daily:
        raise ValueError("no daily rows")
    rows = list(daily)[-CONTEXT_DAYS:]
    last_day = date.fromisoformat(rows[-1]["day"])
    by_day = {date.fromisoformat(r["day"]): r for r in rows}
    out: list[float] = [1.0 if target.weekday() == k else 0.0 for k in range(7)]
    m = 2 * math.pi * (target.timetuple().tm_yday / 365.25)
    out += [
        math.sin(m),
        math.cos(m),
        float(is_holiday(target)),
        float(is_holiday(last_day)),
        float((target - last_day).days),
    ]
    for s in STATS:
        xs = [float(r[s]) for r in rows]
        last7 = xs[-7:]
        week_ago = by_day.get(target - timedelta(days=7))
        out += [
            xs[-1],
            float(np.mean(last7)),
            float(np.median(xs)),
            float(np.std(last7)),
            float(week_ago[s]) if week_ago else float(np.mean(last7)),
        ]
    return out


def cdf_at(qvals: Sequence[float], t: float) -> float:
    """Predicted P(X <= t) by linear interpolation of sorted quantile predictions; the
    tails beyond the outer quantiles are halved towards 0 and 1."""
    v = np.sort(np.asarray(qvals, float))  # sorting removes quantile crossing
    qs = np.asarray(QUANTILES)
    if t < v[0]:
        return float(qs[0] / 2)
    if t >= v[-1]:
        return float(1 - (1 - qs[-1]) / 2)
    return float(np.interp(t, v, qs))


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


@dataclass
class PowerModel:
    """Fitted quantile models per statistic plus a calibration map."""

    train_end: date
    models: dict[str, list[Any]] = field(default_factory=dict)
    calib: LogisticRegression | None = None
    n_train: int = 0
    n_calib: int = 0
    #: Model family in the version string; challengers (e.g. LightGBM) use their own.
    family: str = MODEL_FAMILY
    #: Hyperparameters chosen by tuning, if any (shown on the model card).
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def version(self) -> str:
        """Identifies the artefact: family, revision and training cut-off."""
        return f"{self.family}-r{MODEL_REVISION}-{self.train_end.isoformat()}"

    def quantiles(self, stat: str, x: list[float]) -> list[float]:
        """Predicted quantiles of a statistic."""
        arr = np.asarray([x])
        return [float(m.predict(arr)[0]) for m in self.models[stat]]

    def raw_probability(self, q: Question, ctx: dict[str, Any]) -> float:
        """Uncalibrated P(YES) from the quantile predictions."""
        stat = str(q.params["stat"])
        thr = float(q.params["reference_mean"]) if q.template == "up_vs_today" else q.threshold
        assert thr is not None
        f = self.cdf(stat, ctx, q.target_date, thr)
        return f if q.comparator == "lt" else 1 - f

    def cdf(self, stat: str, ctx: dict[str, Any], target: date, t: float) -> float:
        """P(stat_D <= t)."""
        return cdf_at(self.quantiles(stat, features(ctx["daily"], target)), t)

    def probability(self, q: Question, ctx: dict[str, Any]) -> float:
        """Calibrated P(YES)."""
        raw = self.raw_probability(q, ctx)
        if self.calib is None:
            return raw
        return float(self.calib.predict_proba([[_logit(raw)]])[0, 1])

    def model_hash(self) -> str:
        """Short hash of the version and training sizes (for forecast meta)."""
        blob = f"{self.version}|{self.n_train}|{self.n_calib}".encode()
        return hashlib.sha256(blob).hexdigest()[:12]


def context_rows(daily: dict[date, list[float]], last: date) -> list[dict[str, Any]]:
    """The context's `daily` list as it would have been with `last` the latest known day."""
    days = [d for d in sorted(daily) if last - timedelta(days=CONTEXT_DAYS + 2) < d <= last]
    return [{"day": d.isoformat(), **day_stats(d, daily[d])} for d in days][-CONTEXT_DAYS:]


def training_rows(
    daily: dict[date, list[float]], first_target: date, last_target: date
) -> tuple[np.ndarray, dict[str, np.ndarray], list[date]]:
    """X, {stat: y}, target dates for every D in range whose D-1 and window are known."""
    xs, ys, targets = [], {s: [] for s in STATS}, []  # type: ignore[var-annotated]
    d = first_target
    while d <= last_target:
        prev = d - timedelta(days=1)
        if d in daily and prev in daily:
            rows = context_rows(daily, prev)
            if len(rows) >= CONTEXT_DAYS - 2:
                xs.append(features(rows, d))
                st = day_stats(d, daily[d])
                for s in STATS:
                    ys[s].append(st[s])
                targets.append(d)
        d += timedelta(days=1)
    return np.asarray(xs), {s: np.asarray(v) for s, v in ys.items()}, targets


def fit_quantiles(
    x: np.ndarray, y: np.ndarray, seed: int = 0, max_iter: int = 150
) -> list[HistGradientBoostingRegressor]:
    """One quantile regressor per level in QUANTILES."""
    out = []
    for q in QUANTILES:
        m = HistGradientBoostingRegressor(
            loss="quantile",
            quantile=q,
            max_iter=max_iter,
            learning_rate=0.05,
            max_leaf_nodes=15,
            min_samples_leaf=20,
            random_state=seed,
        )
        out.append(m.fit(x, y))
    return out


def train(
    domain: PowerDomain,
    train_end: date,
    *,
    history_start: date | None = None,
    folds: int = 4,
    fold_days: int = 60,
    gap_days: int = 7,
    max_iter: int = 150,
    fitter: Callable[[np.ndarray, np.ndarray], list[Any]] | None = None,
    family: str = MODEL_FAMILY,
    params: dict[str, Any] | None = None,
) -> PowerModel:
    """Fit on targets up to `train_end`; calibrate on out-of-fold predictions of the real
    questions in the last `folds` x `fold_days` days (expanding window, `gap_days` gap).

    `fitter(x, y)` returns one fitted regressor per level in QUANTILES (default: the
    histogram gradient boosting of `fit_quantiles`); `family` names the model in its
    version, so a challenger family never collides with the champion's artefacts."""
    if fitter is None:

        def fitter(x: np.ndarray, y: np.ndarray) -> list[Any]:
            return fit_quantiles(x, y, max_iter=max_iter)

    daily = domain.all_days()
    daily = {d: v for d, v in daily.items() if d <= train_end}
    if not daily:
        raise ValueError("no price history")
    start = history_start or min(daily) + timedelta(days=CONTEXT_DAYS + 1)
    raw, ys = [], []
    for k in range(folds, 0, -1):
        f_start = train_end - timedelta(days=k * fold_days) + timedelta(days=1)
        f_end = f_start + timedelta(days=fold_days - 1)
        x, y, _ = training_rows(daily, start, f_start - timedelta(days=gap_days))
        if len(x) < 200:
            continue
        fold_model = PowerModel(
            train_end=f_start, models={s: fitter(x, y[s]) for s in STATS}, family=family
        )
        b = f_start - timedelta(days=1)
        while b < f_end:
            asof = datetime.combine(b, MORNING, tzinfo=UTC)
            for q in domain.generate_questions(b, asof):
                r = domain.resolve(q, FAR)
                if isinstance(r, Resolution):
                    raw.append(fold_model.raw_probability(q, domain.context(q, asof)))
                    ys.append(r.outcome)
            b += timedelta(days=1)
    x, y, targets = training_rows(daily, start, train_end)
    model = PowerModel(
        train_end=train_end,
        n_train=len(targets),
        models={s: fitter(x, y[s]) for s in STATS},
        family=family,
        params=dict(params or {}),
    )
    if len(set(ys)) == 2 and len(ys) >= 50:
        model.calib = LogisticRegression(C=1.0).fit([[_logit(p)] for p in raw], ys)
        model.n_calib = len(ys)
    return model
