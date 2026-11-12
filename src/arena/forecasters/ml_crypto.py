"""`ml` for crypto (owner request 2026-11-12): EWMA volatility with fat tails; direction 0.5.

The same recipe as the markets model, fixed before any crypto question resolved (I8):

- `bigmove`: P(|ln(P1/P0)| > T). Daily variance is an exponentially weighted moving
  average (lambda = 0.94) of squared daily log returns from the context (crypto trades
  every day, so no weekday scaling). The day's return is modelled as a Student t with 5
  degrees of freedom scaled to that variance.
- `up`: 0.5. No direction model unless a backtest shows skill with an interval excluding
  zero.
"""

from __future__ import annotations

import math
from datetime import date
from itertools import pairwise
from typing import Any

from scipy.stats import t as student_t

from arena.models import Question

VERSION = "crypto-ewma-t5-r1"
LAMBDA = 0.94
DOF = 5.0


def ewma_variance(rows: list[tuple[date, float]], lam: float = LAMBDA) -> float:
    """EWMA of squared daily log returns (oldest first; gaps spread over their days)."""
    if len(rows) < 3:
        raise ValueError("need at least three daily prices")
    var: float | None = None
    for (d0, p0), (d1, p1) in pairwise(rows):
        days = max(1, (d1 - d0).days)
        r2 = math.log(p1 / p0) ** 2 / days
        var = r2 if var is None else lam * var + (1 - lam) * r2
    assert var is not None
    return var


class CryptoModel:
    """Volatility model for `bigmove`; 0.5 for `up`."""

    version = VERSION

    def probability(self, q: Question, ctx: dict[str, Any]) -> float:
        """P(YES) from the daily prices in the context."""
        if q.template == "up":
            return 0.5
        if q.template != "bigmove":
            raise ValueError(f"unknown crypto template {q.template!r}")
        rows = [
            (date.fromisoformat(r["day"]), float(r["price"]))
            for r in ctx.get("daily_usd_00utc", [])
        ]
        sigma = math.sqrt(ewma_variance(rows))
        if sigma <= 0:
            raise ValueError("zero volatility estimate")
        scale = sigma * math.sqrt((DOF - 2) / DOF)
        assert q.threshold is not None
        return float(2 * student_t.sf(q.threshold / scale, DOF))

    def model_hash(self) -> str:
        """No artefact; the version identifies the rule."""
        return VERSION
