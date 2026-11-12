"""Forecaster contract and the history interface the baselines read from."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from arena.ledger.store import Ledger
from arena.models import Forecast, Question, Resolution, Skip, Void


class Forecaster(Protocol):
    """Anything that maps a question to a probability of YES (or a recorded skip)."""

    forecaster_id: str

    def version(self) -> str:
        """Changes whenever the model artefact, LLM model id or prompt version changes."""
        ...

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """Return a forecast created at `asof`, or a Skip with a reason (never a guess)."""
        ...


@dataclass(frozen=True)
class Instance:
    """One past resolved instance of a (domain, template, entity) series."""

    target_date: date
    outcome: int


class History(Protocol):
    """Past outcomes known at `asof`, oldest first."""

    def instances(
        self, domain: str, template: str, entity: str, before: date, asof: datetime
    ) -> Sequence[Instance]:
        """Resolved instances with target_date < `before`, resolved at or before `asof`."""
        ...


class LedgerHistory:
    """History from the live ledger: resolutions written at or before `asof` (no leakage).

    Voided questions are excluded. Only the first resolution of a question counts (SPEC
    7.1: a later revision is recorded as a void but the first resolution is kept).
    """

    def __init__(self, ledger: Ledger) -> None:
        self.ledger = ledger
        self._questions: dict[str, Question] | None = None

    def _load(self) -> tuple[dict[str, Question], list[Resolution], set[str]]:
        questions = {r.question_id: r for _, r in self.ledger.iter_family("questions")
                     if isinstance(r, Question)}  # fmt: skip
        resolutions: list[Resolution] = []
        voided: set[str] = set()
        for _, r in self.ledger.iter_family("resolutions"):
            if isinstance(r, Resolution):
                resolutions.append(r)
            elif isinstance(r, Void) and r.reason_code != "source_revised":
                voided.add(r.question_id)
        return questions, resolutions, voided

    def instances(
        self, domain: str, template: str, entity: str, before: date, asof: datetime
    ) -> Sequence[Instance]:
        """See `History.instances`."""
        questions, resolutions, voided = self._load()
        first: dict[date, Instance] = {}
        for r in sorted(resolutions, key=lambda r: r.resolved_at):
            q = questions.get(r.question_id)
            if q is None or r.question_id in voided or r.resolved_at > asof:
                continue
            if (q.domain, q.template, q.entity) != (domain, template, entity):
                continue
            if q.target_date < before and q.target_date not in first:
                first[q.target_date] = Instance(q.target_date, r.outcome)
        return [first[d] for d in sorted(first)]


class StaticHistory:
    """In-memory history, e.g. produced by replaying past data through a domain."""

    def __init__(self, series: dict[tuple[str, str, str], Sequence[Instance]]) -> None:
        self.series = {k: sorted(v, key=lambda i: i.target_date) for k, v in series.items()}

    def instances(
        self, domain: str, template: str, entity: str, before: date, asof: datetime
    ) -> Sequence[Instance]:
        """See `History.instances` (replayed history is known by construction)."""
        return [
            i for i in self.series.get((domain, template, entity), []) if i.target_date < before
        ]
