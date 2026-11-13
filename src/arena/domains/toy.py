"""A tiny deterministic domain used only by tests and the offline e2e run."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from arena.domains.base import AsOfStore, is_degenerate, trailing_frequency
from arena.models import Evidence, Question, Resolution, Void, question_id_for

LOCK = time(9, 30)


def _at(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=UTC)


class ToyDomain:
    """Daily value of series `toy`; question: will D's value exceed the 7-day median?"""

    name = "toy"
    template = "value_gt"
    grace = timedelta(hours=24)

    def __init__(self, store: AsOfStore) -> None:
        self.store = store

    def _daily(self, asof: datetime, days: int) -> list[float]:
        rows = self.store.series("toy", asof, timedelta(days=days))
        return [o.value for o in rows if o.value is not None]

    def generate_questions(self, batch_date: date, asof: datetime) -> list[Question]:
        """One question per batch, or none when history is missing or degenerate."""
        values = self._daily(asof, 7)
        if len(values) < 3:
            return []
        threshold = sorted(values)[len(values) // 2]
        outcomes = [int(v > threshold) for v in self._daily(asof, 30)]
        freq = trailing_frequency(outcomes)
        if is_degenerate(freq):
            return []
        target = batch_date + timedelta(days=1)
        lock = _at(batch_date, LOCK)
        return [
            Question(
                question_id=question_id_for(self.name, self.template, "X", target, 1),
                domain=self.name,
                template=self.template,
                template_version=1,
                entity="X",
                text=f"Will the toy value on {target} (UTC) exceed {threshold}?",
                batch_date=batch_date,
                target_date=target,
                created_at=min(asof, lock),
                lock_time=lock,
                resolve_after=_at(target + timedelta(days=1), time(0)),
                resolution_source="toy",
                resolution_rule="value observed for target_date > threshold (strict)",
                threshold=threshold,
                unit="units",
                comparator="gt",
                params={"window_days": 7},
                base_rate_hint=freq,
                tags=["test"],
            )
        ]

    def context(self, question: Question, asof: datetime) -> dict[str, Any]:
        """Recent values, through the gateway only."""
        rows = self.store.series("toy", asof, timedelta(days=14))
        return {"toy": [(o.observed_at.isoformat(), o.value) for o in rows]}

    def resolve(self, question: Question, now: datetime) -> Resolution | Void | None:
        """Resolve from the value observed on the target date."""
        if now < question.resolve_after:
            return None
        day = _at(question.target_date, time(0))
        rows = [o for o in self.store.series("toy", now) if o.observed_at == day]
        if not rows or rows[-1].value is None:
            if now >= question.resolve_after + self.grace:
                return Void(
                    question_id=question.question_id,
                    reason_code="source_missing",
                    detail="no toy value",
                    voided_at=now,
                )
            return None
        value = rows[-1].value
        assert question.threshold is not None
        return Resolution(
            question_id=question.question_id,
            outcome=1 if value > question.threshold else 0,
            observed_value=value,
            resolved_at=now,
            evidence=Evidence(
                source_url="toy://", snapshot_sha256="0" * 64, values_used={"value": value}
            ),
        )
