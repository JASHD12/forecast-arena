from datetime import UTC, date, datetime, timedelta

from smard_fixtures import fixture_client

from arena.domains.power_history import (
    PRICE_KEY,
    PowerHistory,
    backfill,
    daily_from_store,
    daily_series,
)


def test_daily_series_keeps_only_complete_days() -> None:
    client, _ = fixture_client()
    pts = client.chunk(4169, 1794178800000).points
    days = daily_series(pts)
    assert max(days) == date(2026, 11, 12)
    assert all(len(v) == 24 for v in days.values())


def test_store_respects_availability() -> None:
    client, _ = fixture_client()
    store = PowerHistory(client).store([PRICE_KEY], date(2026, 11, 9), date(2026, 11, 13))
    # Morning of 12 Nov: prices for 12 Nov are known (published 11 Nov), 13 Nov are not.
    morning = datetime(2026, 11, 12, 9, 30, tzinfo=UTC)
    known = daily_from_store(store, PRICE_KEY, morning, 10)
    assert max(known) == date(2026, 11, 12)
    # Morning of 11 Nov: 12 Nov prices were not yet published (14:00 Berlin rule).
    known = daily_from_store(store, PRICE_KEY, morning - timedelta(days=1), 10)
    assert max(known) == date(2026, 11, 11)
    for o in store.series(PRICE_KEY, morning):
        assert o.available_at <= morning


def test_backfill_caches_and_summarises(tmp_path) -> None:
    client, transport = fixture_client(cache_dir=tmp_path / "cache")
    # Serve only the fixture chunks: restrict the index to them.
    until = datetime(2026, 11, 12, 11, tzinfo=UTC)
    fixture_ts = {1766358000000, 1774220400000, 1792360800000, 1794178800000}
    client.index = lambda f: sorted(fixture_ts)  # type: ignore[method-assign]
    s = backfill(client, PRICE_KEY, until=until, sleep=lambda x: None)
    assert s.chunks == 4
    assert s.first_day == date(2025, 12, 22)
    assert s.last_day == date(2026, 11, 12)
    assert "4 chunks" in s.line()
    first = len(transport.urls)
    backfill(client, PRICE_KEY, until=until, sleep=lambda x: None)
    # Second run refetches only the partial (current) chunk.
    assert len(transport.urls) - first == 1
    assert not (tmp_path / "cache").is_relative_to(tmp_path / "x")
