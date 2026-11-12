"""Bright Sky client: DWD observations and DWD MOSMIX forecasts (SPEC 7.2).

Verified on 2026-11-12 (docs/SOURCES.md):
- ``GET https://api.brightsky.dev/weather?dwd_station_id=..&date=..&last_date=..&tz=..``
  returns ``{"weather": [record...], "sources": [source...]}``; both ends are inclusive.
- ``temperature`` is the air temperature at the timestamp (2 m, deg C with ``units=dwd``);
  ``precipitation`` is the total of the previous 60 minutes (mm).
- Each record names its ``source_id``; sources have an ``observation_type`` of
  ``historical`` or ``current`` (observations), ``synop`` or ``forecast`` (MOSMIX).
- ``fallback_source_ids`` marks values filled in from another station.

Licence: DWD open data, CC BY 4.0 with source acknowledgement; Bright Sky is a free,
open-source gateway to it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

from arena.sources.http import HttpClient

BASE = "https://api.brightsky.dev"
ATTRIBUTION = "Deutscher Wetterdienst (DWD), via Bright Sky"
LICENCE = "CC BY 4.0"
BERLIN = ZoneInfo("Europe/Berlin")
OBSERVATION_TYPES = frozenset({"historical", "current"})
FORECAST_TYPES = frozenset({"forecast"})
#: Conservative availability of an hourly observation for historical replays.
OBSERVATION_LAG = timedelta(hours=6)


class BrightSkyError(Exception):
    """The response was missing or malformed."""


@dataclass(frozen=True)
class WxRecord:
    """One hourly record. `ts` is UTC. `kind` is the source's observation type."""

    ts: datetime
    kind: str
    temperature: float | None
    precipitation: float | None
    fallback: frozenset[str]
    wind_gust_speed: float | None = None  # km/h (units=dwd), maximum of the previous hour


@dataclass(frozen=True)
class WxResponse:
    """Parsed response with provenance."""

    url: str
    sha256: str
    records: tuple[WxRecord, ...]


def _num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, int | float):
        raise BrightSkyError(f"non-numeric value {v!r}")
    return float(v)


def parse_weather(payload: object) -> tuple[WxRecord, ...]:
    """Validate a /weather document; records sorted by time."""
    if not isinstance(payload, dict):
        raise BrightSkyError("response is not an object")
    weather, sources = payload.get("weather"), payload.get("sources")
    if not isinstance(weather, list) or not isinstance(sources, list):
        raise BrightSkyError("response without 'weather' and 'sources' lists")
    kinds = {s["id"]: s["observation_type"] for s in sources
             if isinstance(s, dict) and "id" in s and "observation_type" in s}  # fmt: skip
    out = []
    for r in weather:
        if not isinstance(r, dict) or "timestamp" not in r or "source_id" not in r:
            raise BrightSkyError(f"malformed record {r!r}")
        ts = datetime.fromisoformat(r["timestamp"])
        if ts.tzinfo is None:
            raise BrightSkyError("timestamp without UTC offset")
        fb = r.get("fallback_source_ids") or {}
        out.append(WxRecord(ts.astimezone(UTC), kinds.get(r["source_id"], "unknown"),
                            _num(r.get("temperature")), _num(r.get("precipitation")),
                            frozenset(fb) if isinstance(fb, dict) else frozenset(),
                            _num(r.get("wind_gust_speed"))))  # fmt: skip
    return tuple(sorted(out, key=lambda x: x.ts))


class BrightSkyClient:
    """Fetches hourly records for one DWD station and a local-day range."""

    def __init__(self, http: HttpClient, base: str = BASE) -> None:
        self.http = http
        self.base = base.rstrip("/")

    def weather(self, station_id: str, first: date, last: date) -> WxResponse:
        """Records for Berlin days first..last, plus the 00:00 record after `last`."""
        start = datetime.combine(first, time(0), tzinfo=BERLIN)
        end = datetime.combine(last + timedelta(days=1), time(0), tzinfo=BERLIN)
        params = {
            "dwd_station_id": station_id,
            "date": start.isoformat(),
            "last_date": end.isoformat(),
            "tz": "Europe/Berlin",
            "units": "dwd",
        }
        resp = self.http.get(f"{self.base}/weather", params)
        return WxResponse(resp.url, resp.sha256, parse_weather(resp.json()))


@lru_cache(maxsize=8192)
def day_hours_ending(day: date) -> tuple[datetime, ...]:
    """UTC end times of the hours of a Berlin day: 01:00 ... 24:00 local (23/24/25)."""
    start = datetime.combine(day, time(0), tzinfo=BERLIN).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=BERLIN).astimezone(UTC)
    n = int((end - start) / timedelta(hours=1))
    return tuple(start + timedelta(hours=i + 1) for i in range(n))


@dataclass(frozen=True)
class DayValues:
    """Hourly values of one variable for a Berlin day; None marks a missing hour."""

    day: date
    variable: str
    values: tuple[float | None, ...]

    @property
    def missing(self) -> int:
        """Number of missing hours."""
        return sum(1 for v in self.values if v is None)

    @property
    def present(self) -> list[float]:
        """The values that exist."""
        return [v for v in self.values if v is not None]


def day_values(
    records: Sequence[WxRecord], day: date, variable: str, kinds: frozenset[str]
) -> DayValues:
    """Hour-ending records of `day` from sources of the given kinds.

    A value filled in from another station (fallback) counts as missing: questions are
    about one named station.
    """
    by_ts = {r.ts: r for r in records if r.kind in kinds}
    vals: list[float | None] = []
    for ts in day_hours_ending(day):
        r = by_ts.get(ts)
        v = None if r is None or variable in r.fallback else getattr(r, variable)
        vals.append(v)
    return DayValues(day, variable, tuple(vals))


def observation_available_at(ts: datetime) -> datetime:
    """Conservative time an hourly observation could first have been known."""
    return ts + OBSERVATION_LAG
