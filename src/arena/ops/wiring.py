"""Build the live domains and forecasters from settings (used by the CLI and workflows)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta

from arena.config import WEATHER_STATIONS, Settings
from arena.domains.base import AsOfStore, Domain
from arena.domains.power import PowerDomain
from arena.domains.power_history import PRICE_KEY, berlin_date, to_observations
from arena.domains.weather import WeatherDomain, weather_domain_from_responses
from arena.forecasters.base import Forecaster, LedgerHistory
from arena.forecasters.baselines import BaseRate, Persistence
from arena.forecasters.replay import CombinedHistory, ReplayHistory
from arena.ledger import Ledger
from arena.sources.brightsky import BrightSkyClient
from arena.sources.http import HttpClient
from arena.sources.smard import FILTERS, SmardClient, berlin_day_bounds

#: Days of history a live power domain loads: replay window (200) + longest template
#: window (60) + margin.
POWER_HISTORY_DAYS = 280


def power_domain_from_client(
    client: SmardClient, now: datetime, days: int = POWER_HISTORY_DAYS,
    on_skip: Callable[[str], None] | None = None,
) -> PowerDomain:  # fmt: skip
    """A power domain with `days` of price history up to D+1, with chunk evidence."""
    today = berlin_date(now)
    start = berlin_day_bounds(today - timedelta(days=days))[0]
    end = berlin_day_bounds(today + timedelta(days=1))[1]
    store = AsOfStore()
    evidence: dict[date, tuple[str, str]] = {}
    for chunk in client.chunks_for(FILTERS[PRICE_KEY], start, end):
        for obs in to_observations(PRICE_KEY, [p for p in chunk.points if start <= p.start < end]):
            store.add(obs)
        for p in chunk.points:
            evidence[berlin_date(p.start)] = (chunk.url, chunk.sha256)
    return PowerDomain(store, evidence=evidence.get, on_skip=on_skip)


#: Observation days loaded for weather: morning runs replay ~200 batches (each needing a
#: 90-day window); resolve runs only need the last days within the grace period.
WEATHER_DAYS = {"morning": 300, "resolve": 10}


def weather_domain_live(
    client: BrightSkyClient, now: datetime, days: int, with_forecast: bool,
    on_skip: Callable[[str], None] | None = None,
) -> WeatherDomain:  # fmt: skip
    """Fetch observations (and tomorrow's MOSMIX forecast) for every station."""
    today = berlin_date(now)
    obs, fc = {}, {}
    for city, (station, _) in WEATHER_STATIONS.items():
        obs[city] = client.weather(station, today - timedelta(days=days), today)
        if with_forecast:
            tomorrow = today + timedelta(days=1)
            fc[city] = client.weather(station, tomorrow, tomorrow)
    return weather_domain_from_responses(WEATHER_STATIONS, obs, fc, now, on_skip=on_skip)


def build_domains(
    settings: Settings, now: datetime, on_skip: Callable[[str], None] | None = None,
    job: str = "morning",
) -> list[Domain]:  # fmt: skip
    """The domains enabled in settings, loaded from the live sources (with the cache)."""
    http = HttpClient(settings.user_agent())
    out: list[Domain] = []
    for name in settings.domains:
        if name == "power":
            client = SmardClient(http, cache_dir=settings.cache_dir)
            out.append(power_domain_from_client(client, now, on_skip=on_skip))
        elif name == "weather":
            out.append(weather_domain_live(BrightSkyClient(http), now, WEATHER_DAYS[job],
                                           job == "morning", on_skip=on_skip))  # fmt: skip
        else:
            raise ValueError(f"domain {name!r} is not available yet")
    return out


def build_forecasters(ledger: Ledger, domains: Sequence[Domain]) -> list[Forecaster]:
    """Baselines over live history, filled with replayed history (SPEC 8.1)."""
    history = CombinedHistory(LedgerHistory(ledger), [ReplayHistory(d) for d in domains])
    return [BaseRate(history), Persistence(history)]
