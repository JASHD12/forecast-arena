"""Uncertainty for scores (SPEC 10): day-block bootstrap with a fixed seed.

Questions from the same day are correlated, so days are resampled, not questions.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Sequence
from dataclasses import dataclass

import numpy as np

REPLICATES = 2000
SEED = 20261112


@dataclass(frozen=True)
class Interval:
    """A point estimate with a 95% percentile interval."""

    estimate: float
    low: float
    high: float
    n: int
    days: int

    @property
    def excludes_zero(self) -> bool:
        """True when the interval lies entirely above or below zero."""
        return self.low > 0 or self.high < 0


def _clip(p: np.ndarray) -> np.ndarray:
    return np.clip(p, 0.01, 0.99)


def day_block_bootstrap(
    days: Sequence[Hashable],
    values: Sequence[float],
    *,
    replicates: int = REPLICATES,
    seed: int = SEED,
) -> Interval:
    """Mean of `values` with a day-block bootstrap interval."""
    if not values:
        raise ValueError("no values")
    keys = sorted(set(days), key=str)
    idx = {k: i for i, k in enumerate(keys)}
    day_ix = np.array([idx[d] for d in days])
    v = np.asarray(values, dtype=float)
    sums = np.bincount(day_ix, weights=v, minlength=len(keys))
    counts = np.bincount(day_ix, minlength=len(keys)).astype(float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(keys), size=(replicates, len(keys)))
    est = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    lo, hi = np.percentile(est, [2.5, 97.5])
    return Interval(float(v.mean()), float(lo), float(hi), len(v), len(keys))


def brier_terms(p: Sequence[float], y: Sequence[int]) -> list[float]:
    """Per-forecast squared errors on clipped probabilities."""
    return list((_clip(np.asarray(p, float)) - np.asarray(y, float)) ** 2)


def paired_brier_difference(
    days: Sequence[Hashable], p_a: Sequence[float], p_b: Sequence[float], y: Sequence[int],
    **kw: int,
) -> Interval:  # fmt: skip
    """Brier(a) - Brier(b) on the same questions, with a day-block interval (negative: a
    is better)."""
    a, b = brier_terms(p_a, y), brier_terms(p_b, y)
    return day_block_bootstrap(days, [x - z for x, z in zip(a, b, strict=True)], **kw)


@dataclass(frozen=True)
class DMResult:
    """Diebold-Mariano test result (two-sided)."""

    statistic: float
    p_value: float
    days: int
    lags: int


def diebold_mariano(
    days: Sequence[Hashable], loss_a: Sequence[float], loss_b: Sequence[float]
) -> DMResult | None:
    """Diebold-Mariano test of equal predictive accuracy (Diebold & Mariano 1995) with the
    Harvey-Leybourne-Newbold (1997) small-sample correction.

    Loss differences are first averaged per batch day (forecasts made on the same day
    are correlated), giving a daily series d_t. The long-run variance of its mean uses a
    Newey-West (Bartlett) estimator with floor(T^(1/3)) lags; the statistic is compared
    with a Student t on T - 1 degrees of freedom. Supplementary to the day-block bootstrap
    (backtest reports only; SPEC 10 headline rules are unchanged). None if T < 3 or the
    variance is zero."""
    from scipy.stats import t as student_t

    by: dict[Hashable, list[float]] = {}
    for d, a, b in zip(days, loss_a, loss_b, strict=True):
        by.setdefault(d, []).append(a - b)
    series = np.asarray([float(np.mean(by[k])) for k in sorted(by, key=str)])
    n = len(series)
    if n < 3:
        return None
    lags = int(n ** (1 / 3))
    dc = series - series.mean()
    lrv = float(dc @ dc) / n
    for k in range(1, lags + 1):
        lrv += 2 * (1 - k / (lags + 1)) * float(dc[k:] @ dc[:-k]) / n
    if lrv <= 0:
        return None
    dm = series.mean() / math.sqrt(lrv / n)
    h = 1  # one-step-ahead forecasts
    hln = math.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    stat = float(dm * hln)
    p = float(2 * student_t.sf(abs(stat), n - 1))
    return DMResult(stat, p, n, lags)


def days_needed(
    daily_diffs: Sequence[float], effect: float, *, alpha: float = 0.05, power: float = 0.8
) -> int | None:
    """Days of data needed to detect a mean daily Brier difference of `effect` with a
    two-sided test at level `alpha` and the given power, from the observed day-to-day
    standard deviation: n = ((z_{1-alpha/2} + z_power) * sd / effect)^2. Normal
    approximation; None with fewer than 3 days or no variation."""
    from scipy.stats import norm

    d = np.asarray(daily_diffs, float)
    if len(d) < 3 or effect <= 0:
        return None
    sd = float(d.std(ddof=1))
    if sd <= 0:
        return None
    z = float(norm.ppf(1 - alpha / 2) + norm.ppf(power))
    return math.ceil((z * sd / effect) ** 2)


# ----- calibration (SPEC 10) ---------------------------------------------------------
@dataclass(frozen=True)
class Bin:
    """One reliability-diagram bin."""

    low: float
    high: float
    n: int
    mean_forecast: float
    observed_rate: float


def calibration_bins(
    p: Sequence[float], y: Sequence[int], bins: int = 10, min_count: int = 10
) -> list[Bin]:
    """Equal-width bins on clipped probabilities; bins with fewer than `min_count` forecasts
    are merged into a neighbour (forward, the last one backward)."""
    if not p or len(p) != len(y):
        raise ValueError("need equally long, non-empty inputs")
    pc = _clip(np.asarray(p, float))
    yy = np.asarray(y, float)
    idx = np.minimum((pc * bins).astype(int), bins - 1)
    groups: list[list[int]] = [list(np.flatnonzero(idx == b)) for b in range(bins)]
    edges = [(b / bins, (b + 1) / bins) for b in range(bins)]
    merged: list[tuple[float, float, list[int]]] = []
    pending: list[int] = []
    low = 0.0
    for (lo, hi), g in zip(edges, groups, strict=True):
        if not pending:
            low = lo
        pending += g
        if len(pending) >= min_count:
            merged.append((low, hi, pending))
            pending = []
    if pending:
        if merged:
            lo0, _, g0 = merged.pop()
            merged.append((lo0, 1.0, g0 + pending))
        else:
            merged.append((low, 1.0, pending))
    return [
        Bin(lo, hi, len(g), float(pc[g].mean()), float(yy[g].mean())) for lo, hi, g in merged if g
    ]


def expected_calibration_error(p: Sequence[float], y: Sequence[int], **kw: int) -> float:
    """Sum over bins of (share of forecasts) x |mean forecast - observed rate|."""
    bs = calibration_bins(p, y, **kw)
    n = sum(b.n for b in bs)
    return sum(b.n / n * abs(b.mean_forecast - b.observed_rate) for b in bs)


@dataclass(frozen=True)
class Murphy:
    """Brier = reliability - resolution + uncertainty (exact for binned-constant forecasts)."""

    reliability: float
    resolution: float
    uncertainty: float

    @property
    def brier(self) -> float:
        """The implied Brier score."""
        return self.reliability - self.resolution + self.uncertainty


def murphy(p: Sequence[float], y: Sequence[int], **kw: int) -> Murphy:
    """Murphy decomposition over the calibration bins."""
    bs = calibration_bins(p, y, **kw)
    n = sum(b.n for b in bs)
    base = float(np.mean(y))
    rel = sum(b.n / n * (b.mean_forecast - b.observed_rate) ** 2 for b in bs)
    res = sum(b.n / n * (b.observed_rate - base) ** 2 for b in bs)
    return Murphy(rel, res, base * (1 - base))
