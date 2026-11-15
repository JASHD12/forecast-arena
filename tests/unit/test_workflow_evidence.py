import json
from datetime import UTC, date, datetime, time, timedelta

import pytest
from factories import forecast, question
from workflow_fixtures import healthy_audit

from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.ledger.manifest import code_sha, manifests_for_day
from arena.ledger.seal import seal_day
from arena.ledger.verify import verify
from arena.ops.health import CORE_FORECASTERS, run_checks
from arena.ops.jobs import resolve
from arena.ops.official import record_health
from arena.ops.workflow_evidence import (
    _items,
    audit_reasons,
    audits,
    collect_audit,
    record_execution,
    save_audit,
    workflow_day_reasons,
)

DAY = date(2026, 11, 16)
NOW = datetime(2026, 11, 17, 5, tzinfo=UTC)


@pytest.mark.parametrize("stage", ["prepare sources", "build site", "deploy", "smoke"])
def test_complete_workflow_failure_cannot_be_hidden_by_passing_health(stage) -> None:
    audit = healthy_audit(DAY)
    audit.attempts[0].stages[stage] = "failure"
    assert any("workflow failed" in r for r in audit_reasons(audit))
    # Neither a subsequent successful retry nor a new observation erases failure.
    audit.attempts[0].conclusion = "failure"
    good = healthy_audit(DAY, NOW)
    assert any("failed workflow attempt" in r for r in workflow_day_reasons([audit, good], DAY))


def test_inventory_missing_modes_incidents_and_required_work_fail_closed() -> None:
    assert workflow_day_reasons([], DAY) == ["no complete workflow outcome evidence"]
    good = healthy_audit(DAY)
    assert audit_reasons(good) == []
    for key, value in [
        ("inventory_complete", False),
        ("expected_attempts", []),
        ("incident_numbers", [7]),
    ]:
        audit = good.model_copy(deep=True)
        setattr(audit, key, value)
        assert audit_reasons(audit)
    audit = good.model_copy(deep=True)
    audit.attempts[0].mode = "unknown"
    assert audit_reasons(audit)
    audit = good.model_copy(deep=True)
    audit.attempts[0].health = None
    assert any("health" in r for r in audit_reasons(audit))
    audit = good.model_copy(deep=True)
    audit.attempts[0].health = {"ok": True, "checks": []}
    assert any("roster" in r for r in audit_reasons(audit))


def test_dry_runs_and_gate_noops_do_not_replace_required_work() -> None:
    audit = healthy_audit(DAY)
    extra = audit.attempts[0].model_copy(deep=True)
    extra.key = "dry:1"
    extra.mode, extra.conclusion = "dry-run", "failure"
    extra.health, extra.code_sha = None, None
    audit.attempts.append(extra)
    extra2 = extra.model_copy(deep=True)
    extra2.key, extra2.mode, extra2.conclusion, extra2.no_op = "noop:1", "live", "success", True
    extra2.stages = {"gate": "success", "run": "skipped"}
    audit.attempts.append(extra2)
    audit.expected_attempts = [a.key for a in audit.attempts]
    assert audit_reasons(audit) == []
    audit.attempts = audit.attempts[-2:]
    audit.expected_attempts = [a.key for a in audit.attempts]
    assert any("missing completed workflow work" in r for r in audit_reasons(audit))


def test_audits_append_on_observation_day_and_preserve_sealed_work(tmp_path) -> None:
    led = Ledger(tmp_path)
    q = question(batch=DAY)
    led.append(layout.questions_path(DAY), [q])
    seal_day(led, DAY, FixedClock(NOW))
    before = {p: led.read_bytes(p) for p in led.list_files()}
    path = save_audit(led, healthy_audit(DAY, NOW))
    assert layout.day_of(path) == NOW.date()
    assert all(led.read_bytes(p) == b for p, b in before.items())
    assert save_audit(led, healthy_audit(DAY, NOW)) != path
    assert len(audits(led)) == 2 and verify(led).ok


def test_paginated_inventory_preserves_failed_attempts_and_all_health(tmp_path) -> None:
    led = Ledger(tmp_path)
    record_execution(
        led,
        {
            "workflow_run_id": "1",
            "workflow_attempt": "2",
            "job": "morning",
            "intended_date": str(DAY),
            "code_sha": "c" * 40,
        },
        datetime.combine(DAY, time(6), UTC),
    )
    for ok in [False, True]:
        record_health(
            led,
            json.dumps(
                {
                    "workflow_run_id": "1",
                    "workflow_attempt": "2",
                    "ok": ok,
                    "checks": [{"name": "forecaster_coverage", "ok": ok}],
                }
            ),
            "morning",
            DAY,
        )
    seen = []

    def api(endpoint):
        seen.append(endpoint)
        if "/actions/runs?" in endpoint:
            return [
                {
                    "total_count": 1,
                    "workflow_runs": [
                        {"id": 1, "path": ".github/workflows/morning.yml", "run_attempt": 2}
                    ],
                }
            ]
        if endpoint.endswith("/jobs?per_page=100"):
            return [
                {
                    "total_count": 1,
                    "jobs": [
                        {
                            "name": "run",
                            "conclusion": "success",
                            "steps": [{"name": "smoke", "conclusion": "success"}],
                        }
                    ],
                }
            ]
        if "/attempts/" in endpoint:
            number = int(endpoint.rsplit("/", 1)[-1])
            return [
                {
                    "event": "schedule",
                    "created_at": f"{DAY}T05:00:00Z",
                    "run_started_at": f"{DAY}T06:00:00Z",
                    "updated_at": f"{DAY}T06:05:00Z",
                    "status": "completed",
                    "conclusion": "failure" if number == 1 else "success",
                    "head_sha": "b" * 40,
                }
            ]
        if "/issues?" in endpoint:
            return [
                [
                    {
                        "number": 9,
                        "state": "open",
                        "created_at": f"{DAY}T07:00:00Z",
                        "closed_at": None,
                    }
                ]
            ]
        raise AssertionError(endpoint)

    audit = collect_audit(led, "test/repo", DAY, NOW, api=api)
    assert audit.expected_attempts == ["1:1", "1:2"]
    assert audit.attempts[0].conclusion == "failure"
    assert audit.attempts[1].code_sha == "c" * 40
    assert audit.attempts[1].health["ok"] is False
    assert audit.incident_numbers == audit.open_incident_numbers == [9]
    assert any("attempts/1/jobs" in e for e in seen)
    with pytest.raises(ValueError, match="incomplete"):
        _items([{"total_count": 2, "jobs": [{}]}], "jobs")


def test_coverage_detects_absent_ml_independently_of_registered_forecasters(tmp_path) -> None:
    led = Ledger(tmp_path)
    q = question(batch=DAY)
    led.append(layout.questions_path(DAY), [q])
    led.append(layout.forecasts_path(DAY), [forecast(q, f) for f in CORE_FORECASTERS - {"ml"}])
    rep = run_checks(led, "morning", datetime.combine(DAY, time(6), UTC))
    coverage = next(c for c in rep.checks if c.name == "forecaster_coverage")
    assert not coverage.ok and "::ml" in coverage.detail


def test_resolve_crossing_midnight_defers_its_manifest_day(tmp_path) -> None:
    led = Ledger(tmp_path)
    q = question(batch=DAY)
    led.append(layout.questions_path(DAY), [q])
    clock = FixedClock(datetime.combine(DAY, time(23, 59), UTC))

    class SlowDomain:
        name = "power"

        def resolve(self, q, now):
            clock.advance(timedelta(minutes=2))
            return None

    resolve(led, clock, [SlowDomain()])
    assert len(manifests_for_day(led, DAY)) == 1
    assert not led.exists(layout.day_seal_path(DAY))
    resolve(led, clock, [])
    sealed = led.read_bytes(layout.day_seal_path(DAY))
    resolve(led, clock, [])
    assert led.read_bytes(layout.day_seal_path(DAY)) == sealed and verify(led).ok


def test_code_provenance_uses_application_checkout_and_explicit_fallback(
    tmp_path, monkeypatch
) -> None:
    import subprocess

    monkeypatch.setenv("GITHUB_SHA", "event-sha")
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 0, "checkout-sha\n")
    )
    assert code_sha() == "checkout-sha"
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 1, ""))
    assert code_sha(tmp_path) == "unknown"
    monkeypatch.setenv("FORECAST_ARENA_CODE_SHA", "packaged-sha")
    assert code_sha(tmp_path) == "packaged-sha"


def test_old_rerun_and_midnight_failure_are_inventoried_on_both_affected_days(tmp_path) -> None:
    led = Ledger(tmp_path)
    old = DAY - timedelta(days=30)
    following = DAY + timedelta(days=1)
    calls = []

    def api(endpoint):
        calls.append(endpoint)
        if endpoint.endswith("/actions/runs?per_page=100"):
            return [
                {
                    "total_count": 1,
                    "workflow_runs": [
                        {
                            "id": 99,
                            "path": ".github/workflows/resolve.yml",
                            "run_attempt": 2,
                            "updated_at": f"{following}T00:02:00Z",
                        }
                    ],
                }
            ]
        if endpoint.endswith("/attempts/1"):
            return [
                {
                    "event": "workflow_dispatch",
                    "display_title": "resolve / live",
                    "created_at": f"{old}T06:00:00Z",
                    "run_started_at": f"{old}T06:00:00Z",
                    "updated_at": f"{old}T06:02:00Z",
                    "status": "completed",
                    "conclusion": "success",
                    "head_sha": "b" * 40,
                }
            ]
        if endpoint.endswith("/attempts/2"):
            return [
                {
                    "event": "workflow_dispatch",
                    "display_title": "resolve / live",
                    "created_at": f"{old}T06:00:00Z",
                    "run_started_at": f"{DAY}T23:59:00Z",
                    "updated_at": f"{following}T00:02:00Z",
                    "status": "completed",
                    "conclusion": "failure",
                    "head_sha": "b" * 40,
                }
            ]
        if endpoint.endswith("/attempts/2/jobs?per_page=100"):
            return [
                {
                    "total_count": 1,
                    "jobs": [
                        {
                            "name": "run",
                            "conclusion": "failure",
                            "steps": [{"name": "construct sources", "conclusion": "failure"}],
                        }
                    ],
                }
            ]
        if "/issues?" in endpoint:
            return [[]]
        raise AssertionError(endpoint)

    for day in [DAY, following]:
        audit = collect_audit(led, "test/repo", day, NOW + timedelta(days=1), api=api)
        assert [a.key for a in audit.attempts] == ["99:2"]
        assert any("workflow failed" in r for r in audit_reasons(audit))
    assert not any("attempts/1/jobs" in endpoint for endpoint in calls)


def test_stale_pending_run_from_previous_day_blocks_readiness(tmp_path) -> None:
    old = DAY - timedelta(days=1)

    def api(endpoint):
        if endpoint.endswith("/actions/runs?per_page=100"):
            return [
                {
                    "total_count": 1,
                    "workflow_runs": [
                        {
                            "id": 7,
                            "path": ".github/workflows/resolve.yml",
                            "run_attempt": 1,
                            "status": "in_progress",
                            "updated_at": f"{old}T23:59:00Z",
                        }
                    ],
                }
            ]
        if endpoint.endswith("/attempts/1"):
            return [
                {
                    "event": "schedule",
                    "created_at": f"{old}T23:58:00Z",
                    "run_started_at": f"{old}T23:59:00Z",
                    "updated_at": f"{old}T23:59:00Z",
                    "status": "in_progress",
                    "conclusion": None,
                    "head_sha": "b" * 40,
                }
            ]
        if endpoint.endswith("/jobs?per_page=100"):
            return [{"total_count": 1, "jobs": [{"name": "run", "conclusion": None}]}]
        if "/issues?" in endpoint:
            return [[]]
        raise AssertionError(endpoint)

    audit = collect_audit(Ledger(tmp_path), "test/repo", DAY, NOW, api=api)
    assert [a.key for a in audit.attempts] == ["7:1"]
    assert any("workflow failed or unfinished" in r for r in audit_reasons(audit))
