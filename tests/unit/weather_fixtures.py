"""Weather domain built from recorded Bright Sky fixtures."""

import gzip
import json
from datetime import UTC, datetime

from brightsky_fixtures import FIXTURES

from arena.config import WEATHER_STATIONS
from arena.domains.weather import WeatherDomain, weather_domain_from_responses
from arena.sources.brightsky import WxResponse, parse_weather

#: The forecast fixtures were fetched at about 11:29 UTC on 2026-11-12.
FC_FETCHED = datetime(2026, 11, 12, 11, 29, tzinfo=UTC)


def _resp(name: str) -> WxResponse:
    path = FIXTURES / name
    raw = gzip.decompress(path.read_bytes()) if name.endswith(".gz") else path.read_bytes()
    return WxResponse(f"fixture://{name}", "f" * 64, parse_weather(json.loads(raw)))


def fixture_weather(skips: list[str] | None = None, forecast_at=FC_FETCHED) -> WeatherDomain:
    obs, fc = {}, {}
    for city, (sid, _) in WEATHER_STATIONS.items():
        obs[city] = _resp(f"obs_{sid}_2026-08-08.json.gz")
        fc[city] = _resp(f"fc_{sid}_2026-11-13.json")
    return weather_domain_from_responses(
        WEATHER_STATIONS,
        obs,
        fc,
        forecast_at,
        on_skip=(skips.append if skips is not None else None),
    )
