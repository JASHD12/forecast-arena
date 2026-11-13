import json
from datetime import UTC, datetime, timedelta

from factories import B, forecast, question

from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.ledger.seal import seal_batch
from arena.models import Skip
from arena.ops.health import INCIDENT_LABEL, INCIDENT_TITLE, run_checks, sync_incident

AFTER_LOCK = datetime(2026, 11, 12, 12, 30, tzinfo=UTC)


def _ledger(tmp_path, seal_at=datetime(2026, 11, 12, 5, 35, tzinfo=UTC), skips=()):
    led = Ledger(tmp_path / "l")
    q = question()
    led.append(layout.questions_path(B), [q])
    led.append(layout.forecasts_path(B), [forecast(q), *skips])
    seal_batch(led, B, FixedClock(seal_at))
    return led, q


def by_name(rep):
    return {c.name: c for c in rep.checks}


def test_healthy_ledger_passes(tmp_path) -> None:
    led, _ = _ledger(tmp_path)
    rep = run_checks(led, "resolve", AFTER_LOCK)
    assert rep.ok, rep.markdown()
    assert "sealed at 05:35" in by_name(rep)["batch_sealed"].detail


def test_each_failure_is_detected(tmp_path) -> None:
    led, _ = _ledger(tmp_path / "late", seal_at=datetime(2026, 11, 12, 10, tzinfo=UTC))
    assert not by_name(run_checks(led, "resolve", AFTER_LOCK))["batch_sealed"].ok

    empty = Ledger(tmp_path / "empty")
    assert (
        "no questions" in by_name(run_checks(empty, "morning", AFTER_LOCK))["batch_sealed"].detail
    )
    before = datetime(2026, 11, 12, 3, 30, tzinfo=UTC)
    assert by_name(run_checks(empty, "resolve", before))["batch_sealed"].ok  # not due yet

    led2, q2 = _ledger(tmp_path / "old")
    later = q2.resolve_after + timedelta(days=6)
    rep = run_checks(led2, "resolve", later)
    assert not by_name(rep)["nothing_overdue"].ok and q2.question_id in rep.markdown()
    assert not by_name(rep)["sources_fresh"].ok  # nothing asked for 6+ days

    led3 = Ledger(tmp_path / "parse")
    qs = [question(entity=f"E{i}") for i in range(6)]
    t = datetime(2026, 11, 12, 5, 33, tzinfo=UTC)
    skips = [
        Skip(question_id=x.question_id, forecaster_id="llm_plain",
             reason_code="parse_failure", detail="not JSON", created_at=t)
        for x in qs[1:]
    ]  # fmt: skip
    led3.append(layout.questions_path(B), qs)
    led3.append(layout.forecasts_path(B), [forecast(qs[0], "llm_plain", 0.4), *skips])
    seal_batch(led3, B, FixedClock(t))
    pf = by_name(run_checks(led3, "resolve", AFTER_LOCK))["parse_failures"]
    assert not pf.ok and "5 of 6" in pf.detail
    few = Ledger(tmp_path / "few")
    few.append(layout.questions_path(B), qs[:2])
    few.append(layout.forecasts_path(B), skips[:1])
    seal_batch(few, B, FixedClock(t))
    assert by_name(run_checks(few, "resolve", AFTER_LOCK))["parse_failures"].ok  # tiny sample
    forced = run_checks(few, "resolve", AFTER_LOCK, force_fail=True)
    assert not forced.ok and forced.failed()[-1].name == "forced_failure"


class FakeGh:
    def __init__(self, issues=()):
        self.issues = list(issues)
        self.calls = []

    def __call__(self, args):
        self.calls.append(list(args))
        if args[:2] == ["issue", "list"]:
            return json.dumps(self.issues)
        if args[:2] == ["issue", "create"]:
            self.issues.append({"number": 7, "title": args[args.index("--title") + 1]})
        if args[:2] == ["issue", "close"]:
            self.issues = [i for i in self.issues if str(i["number"]) != args[2]]
        return ""


def test_incident_opens_once_comments_then_closes() -> None:
    gh = FakeGh()
    assert sync_incident(False, "broken", run=gh) == "opened"
    create = next(c for c in gh.calls if c[:2] == ["issue", "create"])
    assert INCIDENT_TITLE in create and INCIDENT_LABEL in create
    assert sync_incident(False, "still broken", run=gh) == "commented on 7"
    assert sum(c[:2] == ["issue", "create"] for c in gh.calls) == 1  # deduplicated
    assert sync_incident(True, "fine", run=gh) == "closed 7"
    assert sync_incident(True, "fine", run=gh) == "healthy, nothing open"
    other = FakeGh([{"number": 3, "title": "something else"}])
    assert sync_incident(True, "fine", run=other) == "healthy, nothing open"
