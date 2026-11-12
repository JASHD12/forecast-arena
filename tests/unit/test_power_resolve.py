from datetime import UTC, date, datetime, time, timedelta

from power_fixtures import fixture_domain

from arena.domains.base import AsOfStore, Observation
from arena.domains.power import GRACE, PowerDomain, day_stats
from arena.domains.power_history import PRICE_KEY
from arena.models import Resolution, Void
from arena.sources.smard import berlin_day_hours


def questions(batch: date):
    dom = fixture_domain()
    asof = datetime.combine(batch, time(5, 30), tzinfo=UTC)
    return dom, {q.template: q for q in dom.generate_questions(batch, asof)}


def test_normal_day_resolves_every_template() -> None:
    dom, qs = questions(date(2026, 11, 11))
    now = datetime(2026, 11, 11, 12, 30, tzinfo=UTC)
    values = dom.observed(date(2026, 11, 12))
    assert values is not None and len(values) == 24
    stats = day_stats(date(2026, 11, 12), values)
    for name, q in qs.items():
        r = dom.resolve(q, now)
        assert isinstance(r, Resolution), name
        assert r.observed_value == stats[q.params["stat"]]
        assert r.evidence.values_used["hours"] == 24
        assert len(r.evidence.snapshot_sha256) == 64
    up = dom.resolve(qs["up_vs_today"], now)
    assert isinstance(up, Resolution)
    assert up.outcome == int(stats["mean"] > qs["up_vs_today"].params["reference_mean"])


def test_not_before_resolve_after() -> None:
    dom, qs = questions(date(2026, 11, 11))
    early = datetime(2026, 11, 11, 12, 29, tzinfo=UTC)
    assert all(dom.resolve(q, early) is None for q in qs.values())


def test_23_and_25_hour_days() -> None:
    for batch, hours in ((date(2026, 3, 28), 23), (date(2026, 10, 24), 25)):
        dom, qs = questions(batch)
        now = datetime.combine(batch, time(13), tzinfo=UTC)
        r = dom.resolve(qs["mean_gt"], now)
        assert isinstance(r, Resolution)
        assert r.evidence.values_used["hours"] == hours
        assert len(r.evidence.values_used["hourly"]) == hours


def _store_missing_hour(day: date) -> AsOfStore:
    store = AsOfStore()
    for i, h in enumerate(berlin_day_hours(day)):
        if i != 5:
            store.add(Observation(h, h, PRICE_KEY, 100.0))
    return store


def test_missing_hours_wait_then_void() -> None:
    _, qs = questions(date(2026, 11, 11))
    q = qs["mean_gt"]
    broken = PowerDomain(_store_missing_hour(q.target_date))
    assert broken.resolve(q, q.resolve_after + timedelta(hours=1)) is None
    v = broken.resolve(q, q.resolve_after + GRACE)
    assert isinstance(v, Void) and v.reason_code == "source_missing"


def test_ties_are_not_yes() -> None:
    _, qs = questions(date(2026, 11, 11))
    q = qs["mean_gt"]
    store = AsOfStore()
    for h in berlin_day_hours(q.target_date):
        store.add(Observation(h, h, PRICE_KEY, q.threshold))
    r = PowerDomain(store).resolve(q, q.resolve_after)
    assert isinstance(r, Resolution) and r.outcome == 0


def test_revision_detected() -> None:
    dom, qs = questions(date(2026, 11, 11))
    q = qs["max_gt"]
    first = dom.resolve(q, q.resolve_after)
    assert isinstance(first, Resolution)
    assert not dom.revised(q, first)
    h = berlin_day_hours(q.target_date)[3]
    later = q.resolve_after + timedelta(days=2)
    dom.store.add(Observation(later, h, PRICE_KEY, 9999.0))  # SMARD revised one hour
    assert dom.revised(q, first)
