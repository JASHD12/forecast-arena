"""Small builders for valid records, shared by unit tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from arena.models import Evidence, Forecast, Question, Resolution, Skip, question_id_for

B = date(2026, 11, 12)
LOCK = datetime(2026, 11, 12, 9, 30, tzinfo=UTC)


def question(entity: str = "DE_LU", batch: date = B, template: str = "mean_gt") -> Question:
    target = batch + timedelta(days=1)
    lock = datetime(batch.year, batch.month, batch.day, 9, 30, tzinfo=UTC)
    return Question(
        question_id=question_id_for("power", template, entity, target, 1),
        domain="power",
        template=template,
        template_version=1,
        entity=entity,
        text=f"Will the daily mean day-ahead price on {target} exceed 80.0 EUR/MWh?",
        batch_date=batch,
        target_date=target,
        created_at=lock - timedelta(hours=4),
        lock_time=lock,
        resolve_after=lock + timedelta(hours=3),
        resolution_source="smard:4169/DE/hour",
        resolution_rule="mean of hourly prices on target_date (Europe/Berlin) > threshold",
        threshold=80.0,
        unit="EUR/MWh",
        comparator="gt",
        params={"window_days": 28},
        base_rate_hint=0.5,
        tags=["numeric"],
    )


def forecast(q: Question, fid: str = "base_rate", p: float = 0.6, early: int = 2) -> Forecast:
    return Forecast(
        forecast_id=f"{q.question_id}::{fid}",
        question_id=q.question_id,
        forecaster_id=fid,
        forecaster_version="1",
        probability=p,
        created_at=q.lock_time - timedelta(hours=early),
    )


def skip(q: Question, fid: str = "llm_plain") -> Skip:
    return Skip(
        question_id=q.question_id,
        forecaster_id=fid,
        reason_code="model_missing",
        detail="ARENA_LLM_MODEL not set",
        created_at=q.lock_time - timedelta(hours=2),
    )


def resolution(q: Question, outcome: int = 1) -> Resolution:
    return Resolution(
        question_id=q.question_id,
        outcome=outcome,
        observed_value=91.2,
        resolved_at=q.resolve_after + timedelta(minutes=5),
        evidence=Evidence(source_url="https://example.org/x", snapshot_sha256="a" * 64),
    )
