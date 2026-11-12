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


def test_two_v1_templates_per_city_and_deterministic() -> None:
    all_qs = gen(date(2026, 11, 9))
    qs = [q for q in all_qs if q.template in ("tmax_gt", "wet_day")]
    assert len(qs) == 8
    assert {q.template for q in qs} == {"tmax_gt", "wet_day"}
    again = gen(date(2026, 11, 9))
    assert [canonical_json(q) for q in all_qs] == [canonical_json(q) for q in again]
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


V1 = ("tmax_gt", "wet_day")


def test_v1_questions_unchanged_by_new_templates() -> None:
    """`*_v1_frozen.jsonl` are the goldens as recorded before the new templates existed
    (never regenerated): adding templates changed no v1 question."""
    for name, b in CASES.items():
        v1 = "".join(canonical_json(q) for q in gen(b) if q.template in V1)
        assert v1 == (GOLDEN / f"{name}_v1_frozen.jsonl").read_text(encoding="utf-8")


def test_new_templates_generated_and_resolved() -> None:
    dom = fixture_weather()
    qs = gen(date(2026, 11, 9))
    by = {(q.template, q.entity): q for q in qs}
    assert ("gust_gt", "berlin") not in by  # Berlin-Dahlem reports no gusts
    g = by[("gust_gt", "frankfurt")]
    assert g.threshold is not None and g.threshold % 5 == 0 and g.unit == "km/h"
    r = dom.resolve(g, g.resolve_after)
    assert isinstance(r, Resolution)
    assert r.observed_value == max(v for v in r.evidence.values_used["hourly"] if v is not None)
    assert r.outcome == int(r.observed_value > g.threshold)
    f = by[("frost_day", "munich")]
    rf = dom.resolve(f, f.resolve_after)
    assert isinstance(rf, Resolution) and rf.outcome == int(rf.observed_value < 0.0)
    assert rf.observed_value == min(v for v in rf.evidence.values_used["hourly"] if v is not None)
    for t in ("warmer_than", "wetter_than"):
        d = by[(t, "berlin_vs_munich")]
        assert d.params["city_a"] == "berlin" and d.params["city_b"] == "munich"
        rd = dom.resolve(d, d.resolve_after)
        assert isinstance(rd, Resolution)
        va, vb = rd.evidence.values_used["value_a"], rd.evidence.values_used["value_b"]
        assert rd.outcome == int(va > vb)
        assert not dom.revised(d, rd)


def test_duel_tie_is_no_and_missing_station_waits() -> None:
    dom = fixture_weather()
    d = next(q for q in gen(date(2026, 11, 9)) if q.template == "wetter_than")
    r = dom.resolve(d, d.resolve_after)
    assert isinstance(r, Resolution)
    if r.evidence.values_used["value_a"] == r.evidence.values_used["value_b"]:
        assert r.outcome == 0
    store = AsOfStore()
    from arena.domains.weather import WeatherDomain

    empty = WeatherDomain(store, {"berlin": ("00403", "B"), "munich": ("01262", "M")})
    assert empty.resolve(d, d.resolve_after) is None
    v = empty.resolve(d, d.resolve_after + GRACE)
    assert isinstance(v, Void) and v.reason_code == "source_missing"


def test_v1_context_shape_unchanged_and_new_context_has_extras() -> None:
    dom = fixture_weather()
    late = datetime(2026, 11, 12, 11, 30, tzinfo=UTC)
    qs = gen(date(2026, 11, 12))
    t = next(q for q in qs if q.template == "tmax_gt")
    ctx = dom.context(t, late)
    assert list(ctx) == ["domain", "asof", "attribution", "station", "observed_daily",
                         "forecast_daily", "forecast_hourly"]  # fmt: skip
    assert set(ctx["observed_daily"][0]) == {"day", "tmax", "precip"}
    assert set(ctx["forecast_daily"]) == {"tmax", "precip"}
    g = next(q for q in qs if q.template == "gust_gt")
    cg = dom.context(g, late)
    assert {"tmin", "gust_max"} <= set(cg["forecast_daily"])
    d = next(q for q in qs if q.template == "warmer_than")
    cd = dom.context(d, late)
    assert cd["city_a"]["station"] and cd["city_b"]["forecast_daily"]["tmax"] is not None
