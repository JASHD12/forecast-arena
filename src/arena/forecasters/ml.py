"""The `ml` forecaster: dispatches to a per-domain model; `model_missing` skip otherwise."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime
from typing import Any, Protocol

from arena.models import Forecast, Question, Skip


class DomainModel(Protocol):
    """What a fitted per-domain model offers."""

    @property
    def version(self) -> str: ...

    def probability(self, q: Question, ctx: dict[str, Any]) -> float: ...

    def model_hash(self) -> str: ...


class MLForecaster:
    """`ml`: one model family per domain (SPEC 8.3)."""

    forecaster_id = "ml"

    def __init__(
        self,
        models: Mapping[str, DomainModel],
        refresh: Callable[[str, date], DomainModel | None] | None = None,
    ) -> None:
        self.models = dict(models)
        self.refresh = refresh

    def version(self) -> str:
        """All model versions in use, sorted (changes whenever any artefact changes)."""
        return ";".join(sorted(m.version for m in self.models.values())) or "none"

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        if self.refresh is not None:
            fresh = self.refresh(q.domain, asof.date())
            if fresh is not None:
                self.models[q.domain] = fresh
        model = self.models.get(q.domain)
        if model is None:
            return Skip(
                question_id=q.question_id,
                forecaster_id=self.forecaster_id,
                reason_code="model_missing",
                detail=f"no model for {q.domain}",
                created_at=asof,
            )
        try:
            p = model.probability(q, ctx)
        except (ValueError, KeyError) as exc:
            return Skip(
                question_id=q.question_id,
                forecaster_id=self.forecaster_id,
                forecaster_version=model.version,
                reason_code="error",
                detail=f"{type(exc).__name__}: {exc}"[:300],
                created_at=asof,
            )
        if not 0.0 <= p <= 1.0 or p != p:
            return Skip(
                question_id=q.question_id,
                forecaster_id=self.forecaster_id,
                forecaster_version=model.version,
                reason_code="error",
                detail=f"model returned {p!r}",
                created_at=asof,
            )
        return Forecast(
            forecast_id=f"{q.question_id}::{self.forecaster_id}",
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=model.version,
            probability=p,
            created_at=asof,
            meta={"model_hash": model.model_hash()},
        )
