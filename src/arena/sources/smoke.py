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


CHECKS: dict[str, Callable[[HttpClient], str]] = {"smard": check_smard}


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
