"""`ml` for markets (SPEC 8.3): EWMA volatility with fat tails; direction fixed at 0.5.

- `absmove_gt`: P(|ln(F1/F0)| > T). Daily variance is an exponentially weighted moving
  average (RiskMetrics lambda = 0.94) of squared log returns between consecutive fixings,
  each normalised by the number of weekdays it spans. For the question, the variance is
  scaled by the weekdays from F0 to F1 (Friday to Monday is 1; over Easter, Thursday to
  Tuesday is 3). The return is modelled as a Student t with 5 degrees of freedom scaled to
  that variance.
- `up`: 0.5 (H3 is the null test; no direction model is used unless a backtest shows skill
  with an interval excluding zero, docs/project/DECISIONS.md "Markets direction").

Features come only from the context (`fixings` known before the batch day's fixing).
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from itertools import pairwise
from typing import Any

from scipy.stats import t as student_t

from arena.models import Question

VERSION = "markets-ewma-t5-r1"
LAMBDA = 0.94
DOF = 5.0


def weekdays_between(a: date, b: date) -> int:
    """Weekdays in (a, b]; at least 1."""
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return max(1, n)


def ewma_daily_variance(fixings: list[tuple[date, float]], lam: float = LAMBDA) -> float:
    """EWMA of squared per-weekday log returns (oldest first)."""
    if len(fixings) < 3:
        raise ValueError("need at least three fixings")
    var: float | None = None
    for (d0, f0), (d1, f1) in pairwise(fixings):
        r2 = math.log(f1 / f0) ** 2 / weekdays_between(d0, d1)
        var = r2 if var is None else lam * var + (1 - lam) * r2
    assert var is not None
    return var


class MarketsModel:
    """Volatility model for `absmove_gt`; 0.5 for `up`."""

    version = VERSION

    def probability(self, q: Question, ctx: dict[str, Any]) -> float:
        """P(YES) from the fixings in the context."""
        if q.template == "up":
            return 0.5
        if q.template != "absmove_gt":
            raise ValueError(f"unknown markets template {q.template!r}")
        rows = [(date.fromisoformat(r["day"]), float(r["rate"])) for r in ctx.get("fixings", [])]
        var = ewma_daily_variance(rows)
        f0_day = date.fromisoformat(str(q.params["f0_day"]))
        k = weekdays_between(f0_day, q.target_date)
        sigma = math.sqrt(var * k)
        if sigma <= 0:
            raise ValueError("zero volatility estimate")
        scale = sigma * math.sqrt((DOF - 2) / DOF)  # t scale giving standard deviation sigma
        assert q.threshold is not None
        return float(2 * student_t.sf(q.threshold / scale, DOF))

    def model_hash(self) -> str:
        """No artefact; the version identifies the rule."""
        return VERSION
