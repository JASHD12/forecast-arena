"""CoinGecko daily crypto prices (owner request 2026-11-12, DECISIONS.md "Crypto domain").

Verified on 2026-11-12 (docs/SOURCES.md), from docs.coingecko.com:
- Demo API root ``https://api.coingecko.com/api/v3``; key in the header
  ``x-cg-demo-api-key``; 100 calls/min; history limited to the past 365 days.
- ``/coins/{id}/market_chart?vs_currency=usd&days=365&interval=daily`` returns
  ``{"prices": [[unix_ms, price], ...], ...}``; daily points are stamped 00:00 UTC and the
  last element is the current price (not a daily point, ignored here).
- "The last completed UTC day (00:00) is available after 00:35 UTC the next day";
  "values may be revised for up to 2 days after the date".
- Attribution is required when the data is displayed ("Data provided by CoinGecko" with a
  link to coingecko.com).

The API key is optional in code (tests and a one-off local check run keyless); the live
jobs need it (HUMAN_TODO.md H12), because the keyless API is not meant for scheduled use.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from arena.sources.http import HttpClient

BASE = "https://api.coingecko.com/api/v3"
ATTRIBUTION = "Data provided by CoinGecko (coingecko.com)"
LICENCE = "CoinGecko API terms, attribution required"
#: Conservative: the 00:00 UTC point of day X counts as known from X 01:00 UTC
#: (the documentation says after 00:35 UTC).
AVAILABLE_AFTER = timedelta(hours=1)
KEY_HEADER = "x-cg-demo-api-key"


class CoinGeckoError(Exception):
    """A response was missing or malformed."""


@dataclass(frozen=True)
class DailyPrices:
    """Daily 00:00 UTC prices of one coin with provenance."""

    coin: str
    url: str
    sha256: str
    prices: dict[date, float]


def available_at(day: date) -> datetime:
    """When the price stamped 00:00 UTC of `day` is treated as known."""
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC) + AVAILABLE_AFTER


def parse_daily(payload: object) -> dict[date, float]:
    """{UTC day: price} from the points stamped exactly 00:00 UTC."""
    try:
        rows = payload["prices"]  # type: ignore[index]
        out: dict[date, float] = {}
        for ms, price in rows:
            ts = datetime.fromtimestamp(int(ms) / 1000, UTC)
            if (ts.hour, ts.minute, ts.second, ts.microsecond) != (0, 0, 0, 0):
                continue  # the trailing "current price" point
            p = float(price)
            if not p > 0:
                raise CoinGeckoError(f"non-positive price {price!r}")
            out[ts.date()] = p
        return out
    except (KeyError, TypeError, ValueError) as exc:
        raise CoinGeckoError(f"malformed market_chart: {exc}") from exc


class CoinGeckoClient:
    """Fetches daily USD prices; sends the Demo key header when one is configured."""

    def __init__(self, http: HttpClient, api_key: str | None = None, base: str = BASE) -> None:
        self.http = http
        self.api_key = api_key
        self.base = base.rstrip("/")

    def daily(self, coin: str, days: int = 365) -> DailyPrices:
        """The last `days` daily prices of `coin` in USD."""
        url = f"{self.base}/coins/{coin}/market_chart"
        params = {"vs_currency": "usd", "days": str(days), "interval": "daily"}
        headers = {KEY_HEADER: self.api_key} if self.api_key else None
        resp = self.http.get(url, params, headers=headers)
        return DailyPrices(coin, resp.url, resp.sha256, parse_daily(resp.json()))
