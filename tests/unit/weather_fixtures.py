"""Weather domain built from recorded Bright Sky fixtures."""

import dataclasses
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


def _with_gusts(obs: WxResponse, sid: str) -> WxResponse:
    """Merge the gust-only recording (same query, recorded 2026-11-12 ~20:11 UTC)."""
    g = _resp(f"gust_{sid}_2026-08-08.json.gz")
    by_ts = {(r.ts, r.kind): r for r in g.records}
    recs = []
    for r in obs.records:
        m = by_ts.get((r.ts, r.kind))
        if m is None:
            recs.append(r)
            continue
        fb = r.fallback | (m.fallback & {"wind_gust_speed"})
        recs.append(dataclasses.replace(r, wind_gust_speed=m.wind_gust_speed, fallback=fb))
    return WxResponse(obs.url, obs.sha256, tuple(recs))


def fixture_weather(skips: list[str] | None = None, forecast_at=FC_FETCHED) -> WeatherDomain:
    obs, fc = {}, {}
    for city, (sid, _) in WEATHER_STATIONS.items():
        obs[city] = _with_gusts(_resp(f"obs_{sid}_2026-08-08.json.gz"), sid)
        fc[city] = _resp(f"fc_{sid}_2026-11-13.json")
    return weather_domain_from_responses(
        WEATHER_STATIONS,
        obs,
        fc,
        forecast_at,
        on_skip=(skips.append if skips is not None else None),
    )
