from datetime import UTC, date, datetime, timedelta

from power_fixtures import fixture_domain

from arena.clock import FixedClock
from arena.domains.base import template_version_for
from arena.forecasters.base import LedgerHistory
from arena.forecasters.baselines import BaseRate, Persistence
from arena.forecasters.replay import CombinedHistory, ReplayHistory
from arena.ledger import Ledger, layout
from arena.ledger.verify import verify
from arena.models import Forecast, Question, Skip
from arena.ops.health import run_checks
from arena.ops.jobs import evening, morning, resolve

B = date(2026, 11, 2)


class Boom:
    forecaster_id = "boom"

    def version(self) -> str:
        return "1"

    def forecast(self, q, ctx, asof):
        raise RuntimeError("model exploded")


def setup(tmp_path, at: datetime):
    led = Ledger(tmp_path / "ledger")
    dom = fixture_domain()
    hist = CombinedHistory(LedgerHistory(led), [ReplayHistory(dom, days=40)])
    return led, FixedClock(at), [dom], [BaseRate(hist), Persistence(hist), Boom()]


def snapshot(led: Ledger) -> dict[str, bytes]:
    return {f: led.read_bytes(f) for f in led.list_files() if not f.startswith("runs/")}


def test_morning_writes_seals_and_is_idempotent(tmp_path) -> None:
    led, clock, doms, fcs = setup(tmp_path, datetime(2026, 11, 2, 5, 30, tzinfo=UTC))
    r = morning(led, B, clock, doms, fcs)
    assert r.written["questions"] == 6 and r.written["forecasts"] == 18
    assert led.exists(layout.batch_seal_path(B))
    recs = led.read(layout.forecasts_path(B))
    skips = [x for x in recs if isinstance(x, Skip)]
    assert len(skips) == 6 and all(s.reason_code == "error" for s in skips)
    assert all(x.created_at < datetime(2026, 11, 2, 9, 30, tzinfo=UTC) for x in recs)
    base = [x for x in recs if isinstance(x, Forecast) and x.forecaster_id == "base_rate"]
    assert base and all(f.meta["instances"] >= 10 for f in base)  # replayed history
    before = snapshot(led)
    clock.set(datetime(2026, 11, 2, 7, 0, tzinfo=UTC))
    r2 = morning(led, B, clock, doms, fcs)
    assert r2.written == {} and snapshot(led) == before
    assert verify(led).ok


def test_late_run_writes_nothing(tmp_path) -> None:
    led, clock, doms, fcs = setup(tmp_path, datetime(2026, 11, 2, 9, 30, tzinfo=UTC))
    r = morning(led, B, clock, doms, fcs)
    assert r.late and r.written == {}
    assert not led.exists(layout.questions_path(B))
    (manifest,) = led.list_files("runs")
    assert "late run" in led.read_bytes(manifest).decode()


def test_lock_passing_mid_run_discards_forecasts(tmp_path) -> None:
    led, clock, doms, fcs = setup(tmp_path, datetime(2026, 11, 2, 9, 29, tzinfo=UTC))

    class Slow(Boom):
        forecaster_id = "slow"

        def forecast(self, q, ctx, asof):
            clock.set(datetime(2026, 11, 2, 9, 31, tzinfo=UTC))
            raise RuntimeError("too slow")

    r = morning(led, B, clock, doms, [*fcs, Slow()])
    assert r.late
    assert not led.exists(layout.forecasts_path(B))
    assert not led.exists(layout.batch_seal_path(B))


def test_dry_run_touches_nothing(tmp_path) -> None:
    led, clock, doms, fcs = setup(tmp_path, datetime(2026, 11, 2, 5, 30, tzinfo=UTC))
    r = morning(led, B, clock, doms, fcs, dry_run=True)
    assert r.written["questions"] == 6
    assert led.list_files() == []


def test_resolve_then_idempotent_and_seals_days(tmp_path) -> None:
    led, clock, doms, fcs = setup(tmp_path, datetime(2026, 11, 2, 5, 30, tzinfo=UTC))
    morning(led, B, clock, doms, fcs)
    clock.set(datetime(2026, 11, 2, 12, 30, tzinfo=UTC))
    r = resolve(led, clock, doms)
    assert r.written["resolutions"] == 6
    again = resolve(led, clock, doms)
    assert "resolutions" not in again.written
    clock.set(datetime(2026, 11, 3, 3, 30, tzinfo=UTC))
    r3 = resolve(led, clock, doms)
    assert r3.written.get("day_seals") == 1
    assert verify(led).ok


def test_revision_recorded_once(tmp_path) -> None:
    from arena.domains.base import Observation
    from arena.domains.power_history import PRICE_KEY
    from arena.sources.smard import berlin_day_hours

    led, clock, doms, fcs = setup(tmp_path, datetime(2026, 11, 2, 5, 30, tzinfo=UTC))
    morning(led, B, clock, doms, fcs)
    clock.set(datetime(2026, 11, 2, 12, 30, tzinfo=UTC))
    resolve(led, clock, doms)
    h = berlin_day_hours(B + timedelta(days=1))[2]
    clock.set(datetime(2026, 11, 2, 16, 30, tzinfo=UTC))
    doms[0].store.add(Observation(clock.now(), h, PRICE_KEY, 5000.0))  # fetched later
    r = resolve(led, clock, doms)
    assert r.written["resolutions"] == 6  # six source_revised voids
    assert "resolutions" not in resolve(led, clock, doms).written


def test_batch_must_be_today(tmp_path) -> None:
    led, clock, doms, fcs = setup(tmp_path, datetime(2026, 11, 1, 6, 0, tzinfo=UTC))
    r = morning(led, B, clock, doms, fcs)
    assert r.written == {} and "refused" in r.warnings[0]


# ----- T160: evening publication -------------------------------------------------------


def _questions(led: Ledger) -> list[Question]:
    return [q for q in led.read(layout.questions_path(B)) if isinstance(q, Question)]


def test_template_version_follows_publication_time() -> None:
    assert template_version_for(B, datetime(2026, 11, 1, 18, tzinfo=UTC)) == 2
    assert template_version_for(B, datetime(2026, 11, 2, 5, 30, tzinfo=UTC)) == 1


def test_evening_publishes_questions_only_and_morning_forecasts_them(tmp_path) -> None:
    led, clock, doms, fcs = setup(tmp_path, datetime(2026, 11, 1, 18, tzinfo=UTC))
    r = evening(led, B, clock, doms)
    qs = _questions(led)
    assert r.written["questions"] == len(qs) > 0 and not r.warnings
    assert {q.template_version for q in qs} == {2}
    assert {q.lock_time for q in qs} == {datetime(2026, 11, 2, 9, 30, tzinfo=UTC)}
    assert not led.exists(layout.forecasts_path(B)) and not led.exists(layout.batch_seal_path(B))
    before = snapshot(led)
    assert evening(led, B, clock, doms).written == {}  # idempotent
    assert snapshot(led) == before
    rep = run_checks(led, "evening", clock.now())
    assert next(c for c in rep.checks if c.name == "next_batch_published").ok
    clock.set(datetime(2026, 11, 2, 5, 30, tzinfo=UTC))
    m = morning(led, B, clock, doms, fcs)
    assert "questions" not in m.written and m.written["forecasts"] > 0
    assert _questions(led) == qs  # the morning adds no second version
    assert led.exists(layout.batch_seal_path(B))
    assert verify(led).ok


def test_evening_refuses_wrong_day_too_early_and_sealed(tmp_path) -> None:
    led, clock, doms, fcs = setup(tmp_path, datetime(2026, 11, 1, 12, tzinfo=UTC))
    assert "too early" in evening(led, B, clock, doms).warnings[0]
    clock.set(datetime(2026, 10, 31, 18, tzinfo=UTC))
    assert "not tomorrow" in evening(led, B, clock, doms).warnings[0]
    clock.set(datetime(2026, 11, 2, 18, tzinfo=UTC))
    assert "not tomorrow" in evening(led, B, clock, doms).warnings[0]
    assert not led.exists(layout.questions_path(B))
    rep = run_checks(led, "evening", datetime(2026, 11, 1, 18, tzinfo=UTC))
    assert not next(c for c in rep.checks if c.name == "next_batch_published").ok
    clock.set(datetime(2026, 11, 2, 5, 30, tzinfo=UTC))
    morning(led, B, clock, doms, fcs)
    assert {q.template_version for q in _questions(led)} == {1}  # morning fallback
    clock.set(datetime(2026, 11, 1, 18, tzinfo=UTC))  # sealed: nothing more, ever
    assert "already sealed" in evening(led, B, clock, doms).warnings[0]


def test_evening_dry_run_writes_nothing(tmp_path) -> None:
    led, clock, doms, _ = setup(tmp_path, datetime(2026, 11, 1, 18, tzinfo=UTC))
    r = evening(led, B, clock, doms, dry_run=True)
    assert r.written["questions"] > 0
    assert not led.exists(layout.questions_path(B))
