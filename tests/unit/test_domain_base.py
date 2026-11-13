import random
from datetime import UTC, date, datetime, timedelta

import pytest

from arena.domains.base import AsOfStore, DomainRegistry, Observation, is_degenerate
from arena.domains.toy import ToyDomain
from arena.models import Resolution, Void

T0 = datetime(2026, 10, 1, tzinfo=UTC)


def obs(day: int, value: float | None, lag_h: float = 6) -> Observation:
    at = T0 + timedelta(days=day)
    return Observation(
        available_at=at + timedelta(hours=lag_h), observed_at=at, key="toy", value=value
    )


@pytest.mark.parametrize("seed", range(20))
def test_gateway_never_returns_values_newer_than_asof(seed: int) -> None:
    rng = random.Random(seed)
    store = AsOfStore(obs(d, rng.random(), lag_h=rng.uniform(0, 72)) for d in range(60))
    for _ in range(50):
        asof = T0 + timedelta(hours=rng.uniform(0, 60 * 24))
        for o in store.series("toy", asof):
            assert o.available_at <= asof


def test_revision_visible_only_after_it_was_published() -> None:
    store = AsOfStore([obs(0, 1.0, 6), obs(0, 2.0, 48)])
    assert [o.value for o in store.series("toy", T0 + timedelta(hours=7))] == [1.0]
    assert [o.value for o in store.series("toy", T0 + timedelta(hours=49))] == [2.0]


def test_degeneracy_rule() -> None:
    assert is_degenerate(0.05) and is_degenerate(0.95)
    assert not is_degenerate(0.10) and not is_degenerate(0.90) and not is_degenerate(None)


def test_registry() -> None:
    reg = DomainRegistry()
    toy = ToyDomain(AsOfStore())
    reg.register(toy)
    assert reg.enabled(["toy"]) == [toy]
    with pytest.raises(ValueError):
        reg.register(toy)
    with pytest.raises(KeyError):
        reg.get("nope")


def test_toy_domain_end_to_end() -> None:
    store = AsOfStore(obs(d, float(d % 5)) for d in range(36))
    dom = ToyDomain(store)
    batch = date(2026, 11, 5)
    asof = datetime(2026, 11, 5, 6, tzinfo=UTC)
    (q,) = dom.generate_questions(batch, asof)
    assert dom.generate_questions(batch, asof) == [q], "deterministic"
    ctx = dom.context(q, asof)
    assert all(ts < asof.isoformat() for ts, _ in ctx["toy"])
    assert dom.resolve(q, q.resolve_after - timedelta(minutes=1)) is None
    assert dom.resolve(q, q.resolve_after) is None  # 2026-11-06 is day 36: not in store
    store.add(obs(36, 9.0))
    res = dom.resolve(q, q.resolve_after + timedelta(hours=7))
    assert isinstance(res, Resolution) and res.outcome == 1


def test_toy_void_after_grace() -> None:
    store = AsOfStore(obs(d, float(d % 5)) for d in range(35))
    dom = ToyDomain(store)
    (q,) = dom.generate_questions(date(2026, 11, 4), datetime(2026, 11, 4, 6, tzinfo=UTC))
    assert isinstance(dom.resolve(q, q.resolve_after + timedelta(hours=25)), Void)
