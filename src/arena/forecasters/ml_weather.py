"""`ml` for weather (SPEC 8.3), stage 1: transparent rules on the DWD MOSMIX forecast.

Until 60 days of morning snapshots exist (there is no as-of history of forecasts before
that), the weather model is rule-based and its version says so (`weather-rules-r1`). The
rules were fixed before any live question resolved and are not tuned on the live record
(integrity rule I8):

- `tmax_gt`: the forecast daily maximum (highest hour-ending MOSMIX temperature of D) is
  treated as the mean of a normal distribution with a standard deviation of 2.0 C (a
  conservative day-ahead error for a station forecast); P(YES) = P(X > T).
- `wet_day`: a step function of the forecast daily precipitation total (mm):
  < 0.1 -> 0.10, < 0.5 -> 0.30, < 1.0 -> 0.50, < 3.0 -> 0.75, otherwise 0.90.

Without a forecast in the context the model raises, and the `ml` forecaster records an
`error` skip (never a guess).
"""

from __future__ import annotations

import math
from typing import Any

from arena.models import Question

VERSION = "weather-rules-r1"
TMAX_SIGMA = 2.0
WET_STEPS = ((0.1, 0.10), (0.5, 0.30), (1.0, 0.50), (3.0, 0.75))
WET_TOP = 0.90


def normal_sf(x: float) -> float:
    """P(Z > x) for a standard normal Z."""
    return 0.5 * math.erfc(x / math.sqrt(2))


class WeatherRules:
    """Rule-based weather probabilities from the MOSMIX forecast in the context."""

    version = VERSION

    def probability(self, q: Question, ctx: dict[str, Any]) -> float:
        """P(YES) from the forecast for the target day."""
        fc = ctx.get("forecast_daily")
        if not fc:
            raise ValueError("no MOSMIX forecast for the target day in the context")
        if q.template == "tmax_gt":
            assert q.threshold is not None
            return normal_sf((q.threshold - float(fc["tmax"])) / TMAX_SIGMA)
        if q.template == "wet_day":
            mm = float(fc["precip"])
            for upper, p in WET_STEPS:
                if mm < upper:
                    return p
            return WET_TOP
        raise ValueError(f"unknown weather template {q.template!r}")

    def model_hash(self) -> str:
        """Rules have no artefact; the version identifies them."""
        return VERSION
