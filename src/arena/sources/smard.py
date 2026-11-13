"""SMARD client (Bundesnetzagentur electricity market data), SPEC 7.1.

Endpoints, filter ids and behaviour verified on 2026-11-12 (see docs/SOURCES.md):

- index: ``{BASE}/{filter}/{region}/index_{resolution}.json`` -> ``{"timestamps": [ms, ...]}``
- chunk: ``{BASE}/{filter}/{region}/{filter}_{region}_{resolution}_{ts}.json`` ->
  ``{"meta_data": {...}, "series": [[ms, value | null], ...]}``
- Chunks are weekly and start on Monday 00:00 Europe/Berlin; a chunk holds 167, 168 or 169
  hourly values (clock-change weeks). Future hours inside the current chunk are ``null``.

Licence: CC BY 4.0, attribution "Bundesnetzagentur | SMARD.de".
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from arena.sources.http import HttpClient

BASE = "https://www.smard.de/app/chart_data"
ATTRIBUTION = "Bundesnetzagentur | SMARD.de"
LICENCE = "CC BY 4.0"
BERLIN = ZoneInfo("Europe/Berlin")

#: Series used by the project. Ids from github.com/bundesAPI/smard-api, checked live.
FILTERS: dict[str, int] = {
    "price_de_lu": 4169,  # day-ahead price DE/LU, EUR/MWh
    "load": 410,  # total grid load, MWh
    "residual_load": 4359,
    "wind_onshore": 4067,
    "wind_offshore": 1225,
    "solar": 4068,
}

#: Day-ahead prices for delivery day D are published around 13:00 Berlin on D-1. The
#: conservative availability rule for historical replays uses 14:00 Berlin on D-1.
PRICE_AVAILABLE_LOCAL = time(14, 0)
#: Actuals (load, generation) are treated as available two days after the Berlin day ends.
ACTUALS_LAG = timedelta(days=2)


class SmardError(Exception):
    """The SMARD response was missing or malformed."""


@dataclass(frozen=True, order=True)
class Point:
    """One hourly value; `start` is the UTC start of the hour. `value` may be None."""

    start: datetime
    value: float | None


@dataclass(frozen=True)
class Chunk:
    """One weekly chunk with its provenance (used as resolution evidence)."""

    filter_id: int
    timestamp_ms: int
    url: str
    sha256: str
    points: tuple[Point, ...]


def _ms_to_utc(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, UTC)


def parse_index(payload: object) -> list[int]:
    """Validate an index document and return its sorted chunk timestamps (ms)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("timestamps"), list):
        raise SmardError("index without a 'timestamps' list")
    ts = payload["timestamps"]
    if not all(isinstance(t, int) for t in ts):
        raise SmardError("index timestamps must be integers")
    return sorted(ts)


def parse_chunk(payload: object) -> tuple[Point, ...]:
    """Validate a chunk document and return its points in time order (nulls kept)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("series"), list):
        raise SmardError("chunk without a 'series' list")
    points = []
    for row in payload["series"]:
        if not (isinstance(row, list) and len(row) == 2 and isinstance(row[0], int)):
            raise SmardError(f"malformed series row: {row!r}")
        value = row[1]
        if value is not None and not isinstance(value, int | float):
            raise SmardError(f"non-numeric value: {row!r}")
        points.append(Point(_ms_to_utc(row[0]), None if value is None else float(value)))
    return tuple(sorted(points))


class SmardClient:
    """Reads SMARD indexes and weekly chunks through the shared HTTP client.

    With `cache_dir`, chunks are cached on disk once every value in them is non-null
    (a complete past week); the current, partly-null chunk is always fetched fresh.
    """

    def __init__(
        self,
        http: HttpClient,
        *,
        base: str = BASE,
        region: str = "DE",
        resolution: str = "hour",
        cache_dir: Path | None = None,
    ) -> None:
        self.http = http
        self.base = base.rstrip("/")
        self.region = region
        self.resolution = resolution
        self.cache_dir = cache_dir

    def index_url(self, filter_id: int) -> str:
        """URL of the chunk index of a series."""
        return f"{self.base}/{filter_id}/{self.region}/index_{self.resolution}.json"

    def chunk_url(self, filter_id: int, ts: int) -> str:
        """URL of one weekly chunk."""
        r, res = self.region, self.resolution
        return f"{self.base}/{filter_id}/{r}/{filter_id}_{r}_{res}_{ts}.json"

    def index(self, filter_id: int) -> list[int]:
        """Chunk start timestamps (ms) for a series, oldest first."""
        return parse_index(self.http.get(self.index_url(filter_id)).json())

    def chunk(self, filter_id: int, ts: int) -> Chunk:
        """Fetch (or read from cache) one weekly chunk."""
        url = self.chunk_url(filter_id, ts)
        cached = self._cache_path(filter_id, ts)
        if cached is not None and cached.exists():
            meta, body = cached.read_text(encoding="utf-8").split("\n", 1)
            return Chunk(
                filter_id, ts, url, json.loads(meta)["sha256"], parse_chunk(json.loads(body))
            )
        resp = self.http.get(url)
        points = parse_chunk(resp.json())
        chunk = Chunk(filter_id, ts, url, resp.sha256, points)
        if cached is not None and points and all(p.value is not None for p in points):
            cached.parent.mkdir(parents=True, exist_ok=True)
            tmp = cached.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"sha256": resp.sha256}) + "\n" + resp.body.decode(), encoding="utf-8"
            )
            tmp.replace(cached)
        return chunk

    def is_cached(self, filter_id: int, ts: int) -> bool:
        """True if the chunk is in the on-disk cache."""
        path = self._cache_path(filter_id, ts)
        return path is not None and path.exists()

    def _cache_path(self, filter_id: int, ts: int) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / "smard" / str(filter_id) / f"{self.resolution}_{ts}.json"

    def chunks_for(self, filter_id: int, start: datetime, end: datetime) -> list[Chunk]:
        """All chunks overlapping the UTC interval [start, end)."""
        index = self.index(filter_id)
        start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
        wanted = []
        for i, ts in enumerate(index):
            nxt = index[i + 1] if i + 1 < len(index) else None
            if ts < end_ms and (nxt is None or nxt > start_ms):
                wanted.append(ts)
        return [self.chunk(filter_id, ts) for ts in wanted]

    def series(self, filter_id: int, start: datetime, end: datetime) -> list[Point]:
        """Hourly points with start in [start, end), deduplicated and time-ordered."""
        out: dict[datetime, Point] = {}
        for chunk in self.chunks_for(filter_id, start, end):
            for p in chunk.points:
                if start <= p.start < end:
                    out[p.start] = p
        return [out[k] for k in sorted(out)]


def berlin_day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC [start, end) of a Europe/Berlin calendar day (23, 24 or 25 hours)."""
    start = datetime.combine(day, time(0), tzinfo=BERLIN).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time(0), tzinfo=BERLIN).astimezone(UTC)
    return start, end


@lru_cache(maxsize=8192)
def berlin_day_hours(day: date) -> tuple[datetime, ...]:
    """UTC start of every hour of a Europe/Berlin day, in order."""
    start, end = berlin_day_bounds(day)
    n = int((end - start) / timedelta(hours=1))
    return tuple(start + timedelta(hours=i) for i in range(n))


def day_values(points: Iterable[Point], day: date) -> list[float | None]:
    """Values for each hour of the Berlin day, None where missing or null."""
    by_start = {p.start: p.value for p in points}
    return [by_start.get(h) for h in berlin_day_hours(day)]


def complete_day(points: Iterable[Point], day: date) -> list[float] | None:
    """All hourly values of the Berlin day, or None if any hour is missing."""
    values = day_values(points, day)
    if any(v is None for v in values):
        return None
    return [v for v in values if v is not None]


def price_available_at(day: date) -> datetime:
    """Conservative time at which the day-ahead prices for delivery day `day` were known."""
    local = datetime.combine(day - timedelta(days=1), PRICE_AVAILABLE_LOCAL, tzinfo=BERLIN)
    return local.astimezone(UTC)


def actuals_available_at(day: date) -> datetime:
    """Conservative availability time for actuals (load, generation) of a Berlin day."""
    return berlin_day_bounds(day)[1] + ACTUALS_LAG


def latest_complete_day(points: Sequence[Point]) -> date | None:
    """The most recent Berlin day for which every hour has a value."""
    days = sorted({p.start.astimezone(BERLIN).date() for p in points}, reverse=True)
    for d in days:
        if complete_day(points, d) is not None:
            return d
    return None
