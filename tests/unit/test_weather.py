import os
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest
from weather_fixtures import fixture_weather

from arena.domains.base import AsOfStore, Observation
from arena.domains.weather import GRACE, half, obs_key, r1
from arena.models import Resolution, Void, canonical_json
from arena.sources.brightsky import day_hours_ending

GOLDEN = Path(__file__).parents[1] / "fixtures" / "golden" / "weather"
CASES = {"ordinary": date(2026, 11, 9), "forecast_morning": date(2026, 11, 12)}


def gen(batch: date, at: time = time(5, 30), **kw):
    asof = datetime.combine(batch, at, tzinfo=UTC)
    return fixture_weather(**kw).generate_questions(batch, asof)


@pytest.mark.parametrize("name", sorted(CASES))
def test_golden(name: str) -> None:
    got = "".join(canonical_json(q) for q in gen(CASES[name]))
    path = GOLDEN / f"{name}.jsonl"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(got, encoding="utf-8")
    assert got == path.read_text(encoding="utf-8")


def test_two_templates_per_city_and_deterministic() -> None:
    qs = gen(date(2026, 11, 9))
    assert len(qs) == 8
    assert {q.template for q in qs} == {"tmax_gt", "wet_day"}
    assert [canonical_json(q) for q in qs] == [canonical_json(q) for q in gen(date(2026, 11, 9))]
    for q in qs:
        assert q.resolve_after == datetime(2026, 11, 11, 6, tzinfo=UTC)
        assert "°C" in q.text or "mm" in q.text
        if q.template == "tmax_gt":
            assert q.threshold is not None and q.threshold * 2 == int(q.threshold * 2)


def test_window_uses_only_available_observations() -> None:
    for q in gen(date(2026, 11, 9)):
        if "window_end" in q.params:
            assert date.fromisoformat(q.params["window_end"]) <= date(2026, 11, 8)


def test_resolution_from_observations() -> None:
    dom = fixture_weather()
    qs = {q.question_id: q for q in gen(date(2026, 11, 9))}
    q = qs["weather-tmax_gt-berlin-2026-11-10-v1"]
    assert dom.resolve(q, q.resolve_after - timedelta(minutes=1)) is None
    r = dom.resolve(q, q.resolve_after)
    assert isinstance(r, Resolution)
    assert r.evidence.values_used["hours"] == 24
    assert r.observed_value == max(v for v in r.evidence.values_used["hourly"] if v is not None)
    w = dom.resolve(qs["weather-wet_day-berlin-2026-11-10-v1"], q.resolve_after)
    assert isinstance(w, Resolution) and w.outcome == int(w.observed_value >= 1.0)


def test_missing_observations_wait_then_void() -> None:
    dom = fixture_weather()
    q = next(q for q in gen(date(2026, 11, 9)) if q.template == "tmax_gt")
    store = AsOfStore()
    for i, ts in enumerate(day_hours_ending(q.target_date)):
        if i >= 3:  # three missing hours: more than the 2 allowed
            store.add(Observation(ts, ts, obs_key(q.entity, "temperature"), 5.0))
    dom.store = store
    assert dom.resolve(q, q.resolve_after) is None
    v = dom.resolve(q, q.resolve_after + GRACE)
    assert isinstance(v, Void) and v.reason_code == "source_missing"


def test_context_has_forecast_only_after_fetch() -> None:
    q = next(q for q in gen(date(2026, 11, 12)) if q.entity == "berlin")
    dom = fixture_weather()
    early = dom.context(q, datetime(2026, 11, 12, 5, 30, tzinfo=UTC))
    assert early["forecast_daily"] is None  # fixture forecast was fetched at 11:29
    late = dom.context(q, datetime(2026, 11, 12, 11, 30, tzinfo=UTC))
    assert late["forecast_daily"] is not None
    assert len(late["observed_daily"]) == 14


def test_stale_observations_skip() -> None:
    skips: list[str] = []
    assert gen(date(2026, 12, 20), skips=skips) == []
    assert any("stale" in s for s in skips)


def test_rounding() -> None:
    assert half(7.25) == 7.5 and half(7.24) == 7.0 and r1(0.05) == 0.1
