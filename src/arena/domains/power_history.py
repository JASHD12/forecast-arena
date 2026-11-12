"""Power data history: trailing windows for daily jobs and a full-history backfill.

All values reach forecasters through an `AsOfStore`, stamped with the conservative
availability rules of `arena.sources.smard` (documented in docs/SOURCES.md).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from arena.domains.base import AsOfStore, Observation
from arena.sources.smard import (
    BERLIN,
    FILTERS,
    Point,
    SmardClient,
    actuals_available_at,
    berlin_day_bounds,
    berlin_day_hours,
    price_available_at,
)

PRICE_KEY = "price_de_lu"
#: SMARD price history starts with delivery day 2018-10-01.
HISTORY_START = date(2018, 10, 1)


def berlin_date(ts: datetime) -> date:
    """The Europe/Berlin calendar date of an instant."""
    return ts.astimezone(BERLIN).date()


def available_at(key: str, day: date) -> datetime:
    """Conservative availability time of the values of `key` for Berlin day `day`."""
    return price_available_at(day) if key == PRICE_KEY else actuals_available_at(day)


def to_observations(key: str, points: Iterable[Point]) -> list[Observation]:
    """Stamp hourly points with their availability time (nulls are dropped)."""
    return [
        Observation(available_at(key, berlin_date(p.start)), p.start, key, p.value)
        for p in points
        if p.value is not None
    ]


def daily_series(points: Sequence[Point]) -> dict[date, list[float]]:
    """Complete Berlin days only: date -> hourly values (23, 24 or 25 of them)."""
    by_day: dict[date, dict[datetime, float | None]] = {}
    for p in points:
        by_day.setdefault(berlin_date(p.start), {})[p.start] = p.value
    out: dict[date, list[float]] = {}
    for d in sorted(by_day):
        hours = berlin_day_hours(d)
        vals = by_day[d]
        row = [vals.get(h) for h in hours]
        if all(v is not None for v in row):
            out[d] = [v for v in row if v is not None]
    return out


def daily_from_store(
    store: AsOfStore, key: str, asof: datetime, days: int
) -> dict[date, list[float]]:
    """Complete Berlin days of `key` known at `asof`, within the last `days` days."""
    rows = store.series(key, asof, timedelta(days=days + 2))
    pts = [Point(o.observed_at, o.value) for o in rows]
    return daily_series(pts)


class PowerHistory:
    """Fetches SMARD series for Berlin-day ranges and builds as-of stores."""

    def __init__(self, client: SmardClient) -> None:
        self.client = client

    def hourly(self, key: str, first: date, last: date) -> list[Point]:
        """Hourly points for Berlin days first..last inclusive."""
        start = berlin_day_bounds(first)[0]
        end = berlin_day_bounds(last)[1]
        return self.client.series(FILTERS[key], start, end)

    def store(self, keys: Sequence[str], first: date, last: date) -> AsOfStore:
        """An as-of store with every value of `keys` for days first..last."""
        store = AsOfStore()
        for key in keys:
            for obs in to_observations(key, self.hourly(key, first, last)):
                store.add(obs)
        return store

    def trailing_store(self, asof: datetime, days: int = 70, keys: Sequence[str] = (PRICE_KEY,)
                       ) -> AsOfStore:  # fmt: skip
        """The window a daily job needs: `days` Berlin days before `asof` up to D+1.

        Values not yet available at `asof` are still loaded (the gateway hides them), so
        the same store can be used later to resolve.
        """
        today = berlin_date(asof)
        return self.store(keys, today - timedelta(days=days), today + timedelta(days=1))


@dataclass(frozen=True)
class BackfillSummary:
    """What a backfill fetched."""

    key: str
    chunks: int
    first_day: date | None
    last_day: date | None
    complete_days: int
    incomplete_days: list[date]

    def line(self) -> str:
        """One printable summary line."""
        gaps = ", ".join(d.isoformat() for d in self.incomplete_days[:5])
        more = f" (+{len(self.incomplete_days) - 5} more)" if len(self.incomplete_days) > 5 else ""
        return (f"{self.key}: {self.chunks} chunks, days {self.first_day}..{self.last_day}, "
                f"{self.complete_days} complete, {len(self.incomplete_days)} incomplete"
                f"{': ' + gaps + more if gaps else ''}")  # fmt: skip


def backfill(
    client: SmardClient,
    key: str,
    *,
    until: datetime,
    pause: float = 0.25,
    sleep: Callable[[float], None] = time.sleep,
) -> BackfillSummary:
    """Fetch every chunk of a series up to `until` into the client's cache.

    Complete past chunks are cached by the client, so a second run makes no chunk
    requests for them. `pause` keeps request volume polite (SPEC S7).
    """
    if client.cache_dir is None:
        raise ValueError("backfill needs a client with a cache_dir")
    filt = FILTERS[key]
    stamps = [ts for ts in client.index(filt) if ts < until.timestamp() * 1000]
    points: list[Point] = []
    for ts in stamps:
        cached = client.is_cached(filt, ts)
        points.extend(client.chunk(filt, ts).points)
        if not cached and pause:
            sleep(pause)
    known = [p for p in points if p.start < until]
    days = sorted({berlin_date(p.start) for p in known})
    complete = daily_series(known)
    # The last day may legitimately be partial (still being published); not a gap.
    incomplete = [d for d in days[:-1] if d not in complete]
    return BackfillSummary(key, len(stamps), days[0] if days else None,
                           days[-1] if days else None, len(complete), incomplete)  # fmt: skip
