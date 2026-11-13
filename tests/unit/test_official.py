import json
from datetime import UTC, date, datetime, time, timedelta

import pytest
from factories import forecast, question

from arena.clock import FixedClock
from arena.ledger import Ledger, LedgerError, layout
from arena.ledger.manifest import run_manifest
from arena.ledger.seal import seal_batch, seal_day
from arena.ops.official import STREAK, day_statuses, record_health, update_official_start

D0 = date(2026, 11, 13)


def _day(led: Ledger, d: date, *, healthy: bool = True, failed_run: bool = False) -> None:
    """One rehearsal day: questions, a morning run, a health report, then the day seal."""
    morning = datetime.combine(d, time(5, 30), tzinfo=UTC)
    q = question(batch=d)
    with run_manifest(led, "morning", d, FixedClock(morning)):
        led.append(layout.questions_path(d), [q])
        led.append(layout.forecasts_path(d), [forecast(q)])
        seal_batch(led, d, FixedClock(morning + timedelta(minutes=5)))
    if failed_run:
        with pytest.raises(RuntimeError), run_manifest(led, "resolve", d, FixedClock(morning)):
            raise RuntimeError("boom")
    record_health(led, json.dumps({"ok": healthy, "checks": []}), "morning", d)
    seal_day(led, d, FixedClock(datetime.combine(d + timedelta(days=1), time(3, 30), tzinfo=UTC)))


def _days(led: Ledger, n: int, bad: dict[int, str] | None = None) -> None:
    bad = bad or {}
    for i in range(n):
        _day(led, D0 + timedelta(days=i), healthy=bad.get(i) != "incident",
             failed_run=bad.get(i) == "failed")  # fmt: skip


def at(i: int) -> datetime:
    return datetime.combine(D0 + timedelta(days=i), time(4), tzinfo=UTC)


def test_clean_day_reasons(tmp_path) -> None:
    led = Ledger(tmp_path)
    _days(led, 3, {1: "incident", 2: "failed"})
    sts = day_statuses(led, D0, D0 + timedelta(days=3))
    assert [s.clean for s in sts] == [True, False, False, False]
    assert sts[1].reasons == ["a health check failed (incident)"]
    assert any("failed run" in r for r in sts[2].reasons)
    assert "no successful morning run" in sts[3].reasons and "day not sealed" in sts[3].reasons


def test_streak_broken_by_an_incident_then_start_written_once(tmp_path) -> None:
    led = Ledger(tmp_path)
    _days(led, STREAK + 3, {2: "incident"})  # days 0-1 clean, 2 incident, 3..7 clean
    early = update_official_start(led, at(STREAK))  # only days 3, 4 complete after the break
    assert early.start is None and not led.exists(layout.OFFICIAL_START_PATH)
    assert early.streak == 2 and "2 clean day(s)" in early.summary()
    dec = update_official_start(led, at(STREAK + 3))
    expected = D0 + timedelta(days=3 + STREAK)  # day after the 5th clean day after the break
    assert dec.rule == expected and dec.start == expected and dec.written
    data = json.loads(led.read_bytes(layout.OFFICIAL_START_PATH))
    assert data["official_start"] == expected.isoformat()
    again = update_official_start(led, at(STREAK + 9))
    assert again.existing == expected.isoformat() and not again.written
    with pytest.raises(LedgerError):  # the storage itself refuses a second write
        led.write_raw(layout.OFFICIAL_START_PATH, b"{}")


def test_not_before_gate_only_delays(tmp_path) -> None:
    led = Ledger(tmp_path)
    _days(led, STREAK)
    rule = D0 + timedelta(days=STREAK)
    gate = rule + timedelta(days=10)
    dec = update_official_start(led, at(STREAK), not_before=gate)
    assert dec.rule == rule and dec.start == gate and not dec.written
    assert "waiting for the not-before date" in dec.summary()
    assert not led.exists(layout.OFFICIAL_START_PATH)
    led2 = Ledger(tmp_path / "b")
    _days(led2, STREAK)
    dec2 = update_official_start(led2, at(STREAK), not_before=D0)  # earlier gate: no effect
    assert dec2.start == rule and dec2.written
