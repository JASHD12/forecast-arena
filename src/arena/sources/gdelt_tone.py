"""GDELT DOC 2.0 daily news tone and article count per coin (T371, SPEC 7.6).

Verified 2026-11-27 (docs/SOURCES.md, https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/ and
a real response recorded in tests/fixtures/gdelt/, see its provenance.json):
- ``mode=TimelineTone&format=json`` returns ``{"query_details": ..., "timeline": [{"series":
  "Average Tone", "data": [{"date": "20261103T000000Z", "value": -3.0297}, ...]}]}``;
- ``mode=TimelineVolRaw&format=json`` returns the same shape with ``"series": "Article Count"``
  and ``{"date", "value": <articles>, "norm": <all articles monitored that day>}``;
- ``startdatetime``/``enddatetime`` are ``YYYYMMDDHHMMSS``; a range over a week gives daily
  steps; days without matching articles are simply absent (never filled here, I6);
- one request every 5 seconds is the documented limit.

As-of rule (lab/prereg/sentiment.md): the value of UTC day X counts as known from X+1 12:00 UTC
(a 12-hour publication lag, conservative). Only aggregate numbers are handled; no article text.
Attribution: "Data: GDELT Project" with a link to https://www.gdeltproject.org/ (GDELT terms).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from arena.sources.http import HttpClient

BASE = "https://api.gdeltproject.org/api/v2/doc/doc"
ATTRIBUTION = "Data: GDELT Project (gdeltproject.org)"
LICENCE = "GDELT terms: free use, cite the GDELT Project and link https://www.gdeltproject.org/"
#: A day's value is treated as known this long after the day ended (end of day X + 12 hours).
PUBLICATION_LAG = timedelta(hours=12)
#: Seconds between two requests (the documented limit is one per 5 seconds).
REQUEST_PAUSE = 5.5
#: One fixed query per CoinGecko coin id, written down before any feature was computed.
QUERIES: dict[str, str] = {
    "bitcoin": "bitcoin sourcelang:english",
    "ethereum": "ethereum sourcelang:english",
    "solana": "solana crypto sourcelang:english",
    "ripple": "(xrp OR ripple) crypto sourcelang:english",
    "binancecoin": '("binance coin" OR bnb) sourcelang:english',
}
TONE_SERIES = "Average Tone"
COUNT_SERIES = "Article Count"


class GdeltError(Exception):
    """A response was missing or malformed."""


@dataclass(frozen=True)
class DailyNews:
    """Daily average tone and article count of one coin's query, with provenance."""

    coin: str
    tone: dict[date, float]
    count: dict[date, int]
    #: all articles GDELT monitored that day (the ``norm`` field), for context only
    total: dict[date, int]
    urls: tuple[str, ...]
    sha256: tuple[str, ...]


def available_at(day: date) -> datetime:
    """When the value of UTC `day` is treated as known: the end of the day plus the lag."""
    return datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UTC) + (
        PUBLICATION_LAG
    )


def known_days(asof: datetime) -> date:
    """The latest UTC day whose value is known at `asof` (never a day that has not ended)."""
    if asof.tzinfo is None:
        raise ValueError("asof must be timezone-aware")
    return (asof.astimezone(UTC) - PUBLICATION_LAG).date() - timedelta(days=1)


def as_of(series: Mapping[date, float], asof: datetime) -> dict[date, float]:
    """The part of a daily series that was known at `asof` (I3)."""
    last = known_days(asof)
    return {d: v for d, v in series.items() if d <= last}


def _points(payload: object, series: str) -> list[dict[str, object]]:
    try:
        timeline = payload["timeline"]  # type: ignore[index]
        if not timeline:
            return []
        for block in timeline:
            if block["series"] == series:
                return list(block["data"])
    except (KeyError, TypeError) as exc:
        raise GdeltError(f"malformed timeline: {exc}") from exc
    raise GdeltError(f"series {series!r} not in the response")


def _day(stamp: object) -> date:
    try:
        return datetime.strptime(str(stamp), "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC).date()
    except ValueError as exc:
        raise GdeltError(f"unexpected date {stamp!r}") from exc


def parse_tone(payload: object) -> dict[date, float]:
    """{UTC day: average tone} from a TimelineTone response (days without articles absent)."""
    out: dict[date, float] = {}
    for p in _points(payload, TONE_SERIES):
        try:
            out[_day(p["date"])] = float(p["value"])  # type: ignore[arg-type]
        except (KeyError, TypeError, ValueError) as exc:
            raise GdeltError(f"malformed tone point {p!r}") from exc
    return out


def parse_counts(payload: object) -> tuple[dict[date, int], dict[date, int]]:
    """({day: matching articles}, {day: all monitored articles}) from a TimelineVolRaw response."""
    count: dict[date, int] = {}
    total: dict[date, int] = {}
    for p in _points(payload, COUNT_SERIES):
        try:
            d = _day(p["date"])
            count[d] = int(p["value"])  # type: ignore[call-overload]
            total[d] = int(p["norm"])  # type: ignore[call-overload]
        except (KeyError, TypeError, ValueError) as exc:
            raise GdeltError(f"malformed count point {p!r}") from exc
        if count[d] < 0 or total[d] < count[d]:
            raise GdeltError(f"implausible counts {p!r}")
    return count, total


def timeline_url(coin: str, mode: str, start: date, end: date) -> tuple[str, dict[str, str]]:
    """Base URL and parameters of one timeline request for `coin` from `start` to `end`."""
    if coin not in QUERIES:
        raise GdeltError(f"unknown coin {coin!r}")
    return BASE, {
        "query": QUERIES[coin],
        "mode": mode,
        "format": "json",
        "startdatetime": f"{start:%Y%m%d}000000",
        "enddatetime": f"{end:%Y%m%d}235959",
    }


class GdeltClient:
    """Fetches daily tone and article counts, at most one request every `pause` seconds."""

    def __init__(
        self,
        http: HttpClient,
        pause: float = REQUEST_PAUSE,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.http = http
        self.pause = pause
        self.sleep = sleep
        self._requests = 0

    def _get(self, coin: str, mode: str, start: date, end: date) -> tuple[object, str, str]:
        if self._requests:
            self.sleep(self.pause)
        self._requests += 1
        url, params = timeline_url(coin, mode, start, end)
        resp = self.http.get(url, params)
        try:
            return resp.json(), resp.url, resp.sha256
        except ValueError as exc:
            raise GdeltError(f"response is not JSON: {exc}") from exc

    def daily(self, coin: str, start: date, end: date) -> DailyNews:
        """Tone and counts of `coin` for UTC days `start`..`end` (at most ~3 months at a time)."""
        tone_payload, u1, h1 = self._get(coin, "TimelineTone", start, end)
        count_payload, u2, h2 = self._get(coin, "TimelineVolRaw", start, end)
        count, total = parse_counts(count_payload)
        return DailyNews(coin, parse_tone(tone_payload), count, total, (u1, u2), (h1, h2))
