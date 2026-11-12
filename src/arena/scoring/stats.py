"""Uncertainty for scores (SPEC 10): day-block bootstrap with a fixed seed.

Questions from the same day are correlated, so days are resampled, not questions.
"""

from __future__ import annotations

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
