"""The `ml` forecaster: dispatches to a per-domain model; `model_missing` skip otherwise."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from arena.models import Forecast, Question, Skip


class DomainModel(Protocol):
    """What a fitted per-domain model offers."""

    @property
    def version(self) -> str: ...

    def probability(self, q: Question, ctx: dict[str, Any]) -> float: ...

    def model_hash(self) -> str: ...


@dataclass(frozen=True)
class ModelLoadFailure:
    """A promoted model that could not safely be loaded for this run."""

    version: str | None
    detail: str


class MLForecaster:
    """`ml`: one model family per domain (SPEC 8.3)."""

    forecaster_id = "ml"

    def __init__(
        self,
        models: Mapping[str, DomainModel],
        refresh: Callable[[str, date], DomainModel | None] | None = None,
        *,
        load_errors: Mapping[str, ModelLoadFailure] | None = None,
        artifact_hashes: Mapping[str, str] | None = None,
        conformal: Mapping[str, Mapping[str, float]] | None = None,
    ) -> None:
        self.models = dict(models)
        self.refresh = refresh
        self.load_errors = dict(load_errors or {})
        self.artifact_hashes = dict(artifact_hashes or {})
        #: domain -> statistic -> CQR margin of the central 80% band (weekly job), T276b.
        self.conformal = {d: dict(v) for d, v in (conformal or {}).items()}

    def version(self) -> str:
        """All model versions in use, sorted (changes whenever any artefact changes)."""
        return ";".join(sorted(m.version for m in self.models.values())) or "none"

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        if failure := self.load_errors.get(q.domain):
            return Skip(
                question_id=q.question_id,
                forecaster_id=self.forecaster_id,
                forecaster_version=failure.version,
                reason_code="error",
                detail=failure.detail[:300],
                created_at=asof,
            )
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
        meta: dict[str, Any] = {"model_hash": model.model_hash()}
        if artifact_hash := self.artifact_hashes.get(q.domain):
            meta["artifact_sha256"] = artifact_hash
        if interval := self._interval(model, q, ctx):
            meta["interval80"] = interval  # experimental; the probability is unchanged
        return Forecast(
            forecast_id=f"{q.question_id}::{self.forecaster_id}",
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=model.version,
            probability=p,
            created_at=asof,
            meta=meta,
        )

    def _interval(self, model: Any, q: Question, ctx: dict[str, Any]) -> dict[str, Any] | None:
        """Experimental conformal 80% band of the question's statistic, when a margin exists."""
        stat = q.params.get("stat") if q.params else None
        margin = self.conformal.get(q.domain, {}).get(str(stat)) if stat else None
        band = getattr(model, "interval80", None)
        if margin is None or band is None:
            return None
        try:
            lo, hi = band(str(stat), ctx, q.target_date, margin)
        except (ValueError, KeyError):
            return None
        return {
            "stat": str(stat),
            "lo": round(lo, 2),
            "hi": round(hi, 2),
            "margin": round(margin, 2),
            "unit": q.unit,
        }
