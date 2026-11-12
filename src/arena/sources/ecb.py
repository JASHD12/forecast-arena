"""ECB euro foreign exchange reference rates (SPEC 7.4).

Verified on 2026-11-12 (docs/SOURCES.md):
- ``GET https://data-api.ecb.europa.eu/service/data/EXR/D.{CCY+CCY}.EUR.SP00.A
  ?format=csvdata&startPeriod=YYYY-MM-DD&detail=dataonly`` returns CSV with columns
  ``KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE``.
- Rates are set by a concertation around 14:10 CET and published around 16:00 CET on
  every working day except TARGET closing days (New Year's Day, Good Friday, Easter
  Monday, 1 May, 25 and 26 December). The rule matched every weekday since 2019-01-01.
- Terms: free use; the ECB must be cited as the source and modifications (such as
  computed returns) must be stated.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from arena.sources.http import HttpClient

BASE = "https://data-api.ecb.europa.eu/service/data/EXR"
ATTRIBUTION = ("European Central Bank, euro foreign exchange reference rates "
               "(log returns computed by Forecast Arena)")  # fmt: skip
CET = ZoneInfo("Europe/Berlin")
#: Publication is around 16:00 CET; the conservative availability time is 17:00.
AVAILABLE_LOCAL = time(17, 0)


class EcbError(Exception):
    """Malformed response."""


def easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month = (h + m - 7 * n + 114) // 31
    day = (h + m - 7 * n + 114) % 31 + 1
    return date(year, month, day)


def is_target_closing(d: date) -> bool:
    """TARGET closing days on weekdays."""
    e = easter(d.year)
    fixed = (d.month, d.day) in {(1, 1), (5, 1), (12, 25), (12, 26)}
    return fixed or d in (e - timedelta(days=2), e + timedelta(days=1))


def is_publication_day(d: date) -> bool:
    """True on weekdays that are not TARGET closing days."""
    return d.weekday() < 5 and not is_target_closing(d)


def next_publication_day(d: date) -> date:
    """The first publication day strictly after `d`."""
    nxt = d + timedelta(days=1)
    while not is_publication_day(nxt):
        nxt += timedelta(days=1)
    return nxt


def fixing_available_at(d: date) -> datetime:
    """Conservative time the fixing of day `d` could first be known."""
    return datetime.combine(d, AVAILABLE_LOCAL, tzinfo=CET).astimezone(UTC)


def parse_csv(text: str) -> dict[str, dict[date, float]]:
    """{currency: {day: rate}} from a csvdata response."""
    out: dict[str, dict[date, float]] = {}
    try:
        for row in csv.DictReader(io.StringIO(text)):
            if not row.get("OBS_VALUE"):
                continue
            out.setdefault(row["CURRENCY"], {})[date.fromisoformat(row["TIME_PERIOD"])] = float(
                row["OBS_VALUE"])  # fmt: skip
    except (KeyError, ValueError) as exc:
        raise EcbError(f"malformed ECB CSV: {exc}") from exc
    if not out and text.strip() and not text.startswith("KEY"):
        raise EcbError("not an ECB csvdata response")
    return out


@dataclass(frozen=True)
class Rates:
    """Rates with provenance."""

    url: str
    sha256: str
    rates: dict[str, dict[date, float]]


class EcbClient:
    """Fetches daily reference rates for currencies quoted against the euro."""

    def __init__(self, http: HttpClient, base: str = BASE) -> None:
        self.http = http
        self.base = base.rstrip("/")

    def rates(self, currencies: list[str], start: date, end: date | None = None) -> Rates:
        """Daily fixings from `start` (to `end`, if given)."""
        params = {"format": "csvdata", "startPeriod": start.isoformat(), "detail": "dataonly"}
        if end is not None:
            params["endPeriod"] = end.isoformat()
        url = f"{self.base}/D.{'+'.join(currencies)}.EUR.SP00.A"
        resp = self.http.get(url, params)
        return Rates(resp.url, resp.sha256, parse_csv(resp.body.decode("utf-8")))
