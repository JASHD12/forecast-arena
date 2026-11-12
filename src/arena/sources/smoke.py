"""Live source checks for `make smoke-sources`. Uses the network; never part of `make check`."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import timedelta

from arena.clock import SystemClock
from arena.config import Settings
from arena.sources.http import HttpClient
from arena.sources.smard import FILTERS, SmardClient, latest_complete_day


def check_smard(http: HttpClient) -> str:
    """Fetch the latest day-ahead prices and report the latest complete Berlin day."""
    client = SmardClient(http)
    now = SystemClock().now()
    pts = client.series(FILTERS["price_de_lu"], now - timedelta(days=8), now + timedelta(days=2))
    day = latest_complete_day(pts)
    if day is None:
        raise RuntimeError("no complete day in the last 8 days")
    vals = [p.value for p in pts if p.value is not None]
    return f"latest complete day {day}, {len(vals)} hourly prices, last {vals[-1]} EUR/MWh"


def check_weather(http: HttpClient) -> str:
    """Tomorrow's DWD forecast and yesterday's observations for every city (Bright Sky)."""
    from arena.config import WEATHER_STATIONS
    from arena.sources.brightsky import (
        BERLIN,
        FORECAST_TYPES,
        OBSERVATION_TYPES,
        BrightSkyClient,
        day_values,
    )

    client = BrightSkyClient(http)
    today = SystemClock().now().astimezone(BERLIN).date()
    parts = []
    for city, (station, _) in sorted(WEATHER_STATIONS.items()):
        y, t = today - timedelta(days=1), today + timedelta(days=1)
        obs = day_values(client.weather(station, y, y).records, y, "temperature",
                         OBSERVATION_TYPES)  # fmt: skip
        fc = day_values(client.weather(station, t, t).records, t, "temperature", FORECAST_TYPES)
        if not obs.present or not fc.present:
            raise RuntimeError(f"{city}: no observations or no forecast")
        parts.append(f"{city} obs max {max(obs.present)} ({obs.missing} missing), "
                     f"fc max {max(fc.present)}")  # fmt: skip
    return "; ".join(parts)


def check_wikimedia(http: HttpClient) -> str:
    """The latest published top list of each project (looking back up to four days)."""
    from arena.sources.wikimedia import WikimediaClient

    client = WikimediaClient(http)
    today = SystemClock().now().date()
    parts = []
    for project in ("de.wikipedia", "en.wikipedia"):
        for back in range(1, 5):
            day = today - timedelta(days=back)
            arts = client.top(project, day)
            if arts:
                parts.append(f"{project} {day}: {len(arts)} articles, #5 {arts[4].article}")
                break
        else:
            raise RuntimeError(f"{project}: no top list in the last four days")
    return "; ".join(parts)


def check_ecb(http: HttpClient) -> str:
    """The latest EUR/USD and EUR/JPY reference rates."""
    from arena.sources.ecb import EcbClient

    r = EcbClient(http).rates(["USD", "JPY"], SystemClock().now().date() - timedelta(days=10))
    parts = []
    for ccy in ("USD", "JPY"):
        day = max(r.rates[ccy])
        parts.append(f"EUR/{ccy} {day}: {r.rates[ccy][day]}")
    return "; ".join(parts)


CHECKS: dict[str, Callable[[HttpClient], str]] = {
    "ecb": check_ecb,
    "wikimedia": check_wikimedia,
    "smard": check_smard,
    "weather": check_weather,
}


def main(argv: list[str] | None = None) -> int:
    """Run every check (or those named in argv); exit 1 if any fails."""
    names = (argv if argv is not None else sys.argv[1:]) or list(CHECKS)
    http = HttpClient(Settings.from_env().user_agent(), retries=2)
    failed = 0
    for name in names:
        try:
            print(f"{name}: OK - {CHECKS[name](http)}")
        except Exception as exc:  # report every source, then fail
            failed += 1
            print(f"{name}: FAILED - {type(exc).__name__}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
