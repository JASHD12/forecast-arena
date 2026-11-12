"""`ml` for weather (SPEC 8.3), stage 1: transparent rules on the DWD MOSMIX forecast.

Until 60 days of morning snapshots exist (there is no as-of history of forecasts before
that), the weather model is rule-based and its version says so (`weather-rules-r1`, now `r2`). The
rules were fixed before any live question resolved and are not tuned on the live record
(integrity rule I8):

- `tmax_gt`: the forecast daily maximum (highest hour-ending MOSMIX temperature of D) is
  treated as the mean of a normal distribution with a standard deviation of 2.0 C (a
  conservative day-ahead error for a station forecast); P(YES) = P(X > T).
- `wet_day`: a step function of the forecast daily precipitation total (mm):
  < 0.1 -> 0.10, < 0.5 -> 0.30, < 1.0 -> 0.50, < 3.0 -> 0.75, otherwise 0.90.

Added in r2 (2026-11-12, together with the new templates, before any of them resolved;
the r1 rules above are unchanged):

- `frost_day`: forecast daily minimum as the mean of a normal with sd 2.0 C;
  P(YES) = P(X < 0).
- `gust_gt`: forecast highest hourly gust as the mean of a normal with sd 8.0 km/h (gusts
  are harder to forecast than temperature); P(YES) = P(X > T).
- `warmer_than`: the difference of the two forecast maxima as the mean of a normal with sd
  2.0 * sqrt(2) C (two independent station errors); P(YES) = P(X > 0).
- `wetter_than`: if both forecast totals are below 0.1 mm, 0.10 (two dry days are NO);
  otherwise 0.5 + 0.35 * tanh((a - b) / 2 mm).

Without a forecast in the context the model raises, and the `ml` forecaster records an
`error` skip (never a guess).
"""

from __future__ import annotations

import math
from typing import Any

from arena.models import Question

VERSION = "weather-rules-r2"
TMAX_SIGMA = 2.0
TMIN_SIGMA = 2.0
GUST_SIGMA = 8.0
DRY_MM = 0.1
DRY_BOTH = 0.10
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
        if q.template in ("warmer_than", "wetter_than"):
            return self._duel(q, ctx)
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
        if q.template == "frost_day":
            if fc.get("tmin") is None:
                raise ValueError("no forecast minimum temperature in the context")
            return 1.0 - normal_sf((0.0 - float(fc["tmin"])) / TMIN_SIGMA)
        if q.template == "gust_gt":
            assert q.threshold is not None
            if fc.get("gust_max") is None:
                raise ValueError("no forecast gust in the context")
            return normal_sf((q.threshold - float(fc["gust_max"])) / GUST_SIGMA)
        raise ValueError(f"unknown weather template {q.template!r}")

    @staticmethod
    def _duel(q: Question, ctx: dict[str, Any]) -> float:
        fa = (ctx.get("city_a") or {}).get("forecast_daily")
        fb = (ctx.get("city_b") or {}).get("forecast_daily")
        if not fa or not fb:
            raise ValueError("no MOSMIX forecast for both cities in the context")
        if q.template == "warmer_than":
            diff = float(fa["tmax"]) - float(fb["tmax"])
            return normal_sf(-diff / (TMAX_SIGMA * math.sqrt(2)))
        a, b = float(fa["precip"]), float(fb["precip"])
        if a < DRY_MM and b < DRY_MM:
            return DRY_BOTH
        return 0.5 + 0.35 * math.tanh((a - b) / 2.0)

    def model_hash(self) -> str:
        """Rules have no artefact; the version identifies them."""
        return VERSION
