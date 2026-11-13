from datetime import UTC, date, datetime

import pytest
from brightsky_fixtures import fixture_client

from arena.config import WEATHER_STATIONS
from arena.sources.brightsky import (
    FORECAST_TYPES,
    OBSERVATION_TYPES,
    BrightSkyError,
    day_hours_ending,
    day_values,
    parse_weather,
)


def test_hour_ending_grid_handles_clock_changes() -> None:
    assert len(day_hours_ending(date(2026, 11, 10))) == 24
    assert len(day_hours_ending(date(2026, 3, 29))) == 23
    assert len(day_hours_ending(date(2026, 10, 25))) == 25
    assert day_hours_ending(date(2026, 11, 10))[0] == datetime(2026, 11, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize("city", sorted(WEATHER_STATIONS))
def test_observations_for_each_city(city: str) -> None:
    client, transport = fixture_client()
    station = WEATHER_STATIONS[city][0]
    resp = client.weather(station, date(2026, 11, 10), date(2026, 11, 10))
    assert "tz=Europe%2FBerlin" in transport.urls[0] and len(resp.sha256) == 64
    t = day_values(resp.records, date(2026, 11, 10), "temperature", OBSERVATION_TYPES)
    p = day_values(resp.records, date(2026, 11, 10), "precipitation", OBSERVATION_TYPES)
    assert len(t.values) == 24 and t.missing <= 2
    assert len(p.values) == 24
    # Observations never come from forecast sources.
    assert day_values(resp.records, date(2026, 11, 10), "temperature", FORECAST_TYPES).missing == 24


@pytest.mark.parametrize("city", sorted(WEATHER_STATIONS))
def test_forecasts_for_each_city(city: str) -> None:
    client, _ = fixture_client()
    resp = client.weather(WEATHER_STATIONS[city][0], date(2026, 11, 13), date(2026, 11, 13))
    t = day_values(resp.records, date(2026, 11, 13), "temperature", FORECAST_TYPES)
    assert t.missing == 0 and all(-40 < v < 45 for v in t.present)
    assert (
        day_values(resp.records, date(2026, 11, 13), "temperature", OBSERVATION_TYPES).missing == 24
    )


def test_fallback_values_count_as_missing() -> None:
    payload = {
        "sources": [{"id": 1, "observation_type": "historical"}],
        "weather": [
            {
                "timestamp": "2026-11-10T01:00:00+01:00",
                "source_id": 1,
                "temperature": 5.0,
                "precipitation": 0.1,
                "fallback_source_ids": {"temperature": 9},
            },
        ],
    }
    recs = parse_weather(payload)
    t = day_values(recs, date(2026, 11, 10), "temperature", OBSERVATION_TYPES)
    p = day_values(recs, date(2026, 11, 10), "precipitation", OBSERVATION_TYPES)
    assert t.values[0] is None and p.values[0] == 0.1


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"weather": []},
        {"weather": [{"x": 1}], "sources": []},
        {"weather": [{"timestamp": "2026-11-10T01:00:00", "source_id": 1}], "sources": []},
        {
            "weather": [
                {"timestamp": "2026-11-10T01:00:00+01:00", "source_id": 1, "temperature": "warm"}
            ],
            "sources": [],
        },
    ],
)
def test_malformed_rejected(payload) -> None:
    with pytest.raises(BrightSkyError):
        parse_weather(payload)
