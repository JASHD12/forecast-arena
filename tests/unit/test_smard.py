from datetime import UTC, date, datetime

import pytest
from smard_fixtures import fixture_client

from arena.sources.smard import (
    FILTERS,
    SmardError,
    berlin_day_bounds,
    berlin_day_hours,
    complete_day,
    day_values,
    latest_complete_day,
    parse_chunk,
    parse_index,
    price_available_at,
)

PRICE = FILTERS["price_de_lu"]


def test_berlin_days_have_23_24_25_hours() -> None:
    assert len(berlin_day_hours(date(2026, 3, 29))) == 23
    assert len(berlin_day_hours(date(2026, 10, 25))) == 25
    assert len(berlin_day_hours(date(2026, 11, 12))) == 24
    start, end = berlin_day_bounds(date(2026, 11, 12))
    assert start == datetime(2026, 11, 11, 23, tzinfo=UTC)
    assert end == datetime(2026, 11, 12, 23, tzinfo=UTC)


def test_index_and_chunk_selection() -> None:
    client, transport = fixture_client()
    idx = client.index(PRICE)
    assert idx[0] == 1538344800000 and idx == sorted(idx)
    chunks = client.chunks_for(
        PRICE, datetime(2026, 10, 24, tzinfo=UTC), datetime(2026, 10, 25, 22, tzinfo=UTC)
    )
    assert [c.timestamp_ms for c in chunks] == [1792360800000]
    assert all("ForecastArena" in u or "smard.de" in u for u in transport.urls)


def test_clock_change_weeks() -> None:
    client, _ = fixture_client()
    autumn = client.chunk(PRICE, 1792360800000)
    spring = client.chunk(PRICE, 1774220400000)
    assert len(autumn.points) == 169
    assert len(spring.points) == 167
    assert len(complete_day(autumn.points, date(2026, 10, 25)) or []) == 25
    assert len(complete_day(spring.points, date(2026, 3, 29)) or []) == 23
    assert len(autumn.sha256) == 64


def test_nulls_and_latest_complete_day() -> None:
    client, _ = fixture_client()
    chunk = client.chunk(PRICE, 1794178800000)
    assert any(p.value is None for p in chunk.points)
    assert latest_complete_day(chunk.points) == date(2026, 11, 12)
    assert complete_day(chunk.points, date(2026, 11, 13)) is None
    assert day_values(chunk.points, date(2026, 11, 13))[0] is None


def test_series_across_chunks_is_ordered_and_deduplicated() -> None:
    client, _ = fixture_client()
    pts = client.series(
        PRICE, datetime(2026, 11, 9, tzinfo=UTC), datetime(2026, 11, 12, tzinfo=UTC)
    )
    assert [p.start for p in pts] == sorted({p.start for p in pts})
    assert len(pts) == 72


def test_cache_stores_only_complete_chunks(tmp_path) -> None:
    client, transport = fixture_client(cache_dir=tmp_path)
    client.chunk(PRICE, 1792360800000)
    client.chunk(PRICE, 1792360800000)
    client.chunk(PRICE, 1794178800000)
    client.chunk(PRICE, 1794178800000)
    chunk_urls = [u for u in transport.urls if "index" not in u]
    assert sum("1792360800000" in u for u in chunk_urls) == 1  # cached after first read
    assert sum("1794178800000" in u for u in chunk_urls) == 2  # partial: never cached
    cached = client.chunk(PRICE, 1792360800000)
    assert len(cached.points) == 169 and len(cached.sha256) == 64


def test_price_availability_rule() -> None:
    # Prices for 13 Nov are known from 14:00 Berlin on 12 Nov (13:00 UTC in winter).
    assert price_available_at(date(2026, 11, 13)) == datetime(2026, 11, 12, 13, tzinfo=UTC)
    assert price_available_at(date(2026, 7, 2)) == datetime(2026, 7, 1, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "payload",
    [{}, {"timestamps": "x"}, {"timestamps": [1.5]}],
)
def test_bad_index_rejected(payload) -> None:
    with pytest.raises(SmardError):
        parse_index(payload)


@pytest.mark.parametrize(
    "payload",
    [{}, {"series": [[1]]}, {"series": [["a", 1]]}, {"series": [[1, "x"]]}],
)
def test_bad_chunk_rejected(payload) -> None:
    with pytest.raises(SmardError):
        parse_chunk(payload)
