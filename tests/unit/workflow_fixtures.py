"""Complete Actions observations for readiness regression fixtures."""

from datetime import UTC, date, datetime, time, timedelta

from arena.ops.workflow_evidence import Attempt, Audit


def healthy_audit(day: date, observed: datetime | None = None) -> Audit:
    jobs = ["morning", "evening", "resolve"] + (["weekly"] if day.weekday() == 6 else [])
    started = datetime.combine(day, time(6), UTC)
    attempts = [
        Attempt(
            key=f"{day}-{job}:1",
            job=job,
            event="schedule",
            created_at=started,
            started_at=started,
            ended_at=started + timedelta(minutes=5),
            intended_date=day,
            mode="live",
            conclusion="success",
            code_sha="a" * 40,
            event_sha="b" * 40,
            stages={"run": "success", "deploy": "success", "smoke": "success"},
            health={"ok": True, "checks": [{"name": "forecaster_coverage", "ok": True}]},
        )
        for job in jobs
    ]
    return Audit(
        target_day=day,
        observed_at=observed or datetime.combine(day + timedelta(days=1), time(3, 31), UTC),
        inventory_complete=True,
        expected_attempts=[a.key for a in attempts],
        attempts=attempts,
        incident_numbers=[],
        open_incident_numbers=[],
    )
