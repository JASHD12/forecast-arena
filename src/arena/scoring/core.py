"""Scoring v1 (SPEC 10): clipping, Brier, log score, skill against `base_rate`, counts.

Scores are derived data: recomputed from the ledger on every build, never stored in it.
Voided questions are excluded and counted, except `source_revised`, where the first
resolution is kept in the scores (SPEC 7.1).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date

from arena.ledger import Ledger
from arena.models import Forecast, Question, Resolution, Skip, Void

CLIP_LOW, CLIP_HIGH = 0.01, 0.99
REFERENCE = "base_rate"


def clip(p: float) -> float:
    """Clip a probability to [0.01, 0.99] for scoring; raw values stay in the ledger."""
    return min(CLIP_HIGH, max(CLIP_LOW, p))


def brier(ps: Sequence[float], ys: Sequence[int], *, clipped: bool = True) -> float:
    """Mean squared error of (clipped) probabilities against 0/1 outcomes.

    Published scores always clip (SPEC 10). `clipped=False` exposes the bare rule.
    """
    _check(ps, ys)
    f = clip if clipped else float
    return sum((f(p) - y) ** 2 for p, y in zip(ps, ys, strict=True)) / len(ps)


def log_score(ps: Sequence[float], ys: Sequence[int]) -> float:
    """Mean negative log likelihood of the outcomes (lower is better)."""
    _check(ps, ys)
    return -sum(math.log(clip(p) if y else 1 - clip(p)) for p, y in zip(ps, ys, strict=True)) / len(
        ps
    )


def brier_skill(b: float, b_ref: float) -> float | None:
    """1 - Brier / reference Brier; None when the reference is perfect (undefined)."""
    return None if b_ref == 0 else 1 - b / b_ref


def _check(ps: Sequence[float], ys: Sequence[int]) -> None:
    if not ps or len(ps) != len(ys):
        raise ValueError("need equally long, non-empty probabilities and outcomes")
    if any(y not in (0, 1) for y in ys):
        raise ValueError("outcomes must be 0 or 1")


@dataclass(frozen=True)
class Scored:
    """One resolved, non-voided forecast."""

    question_id: str
    forecaster_id: str
    forecaster_version: str
    domain: str
    batch_date: date
    probability: float
    outcome: int


@dataclass
class Record:
    """Everything scoring needs, read once from the ledger."""

    questions: dict[str, Question]
    resolutions: dict[str, Resolution]
    voids: dict[str, Void]
    forecasts: list[Forecast]
    skips: list[Skip]
    scored: list[Scored] = field(default_factory=list)


def load(ledger: Ledger) -> Record:
    """Read questions, forecasts, skips, first resolutions and voids from the ledger."""
    questions = {
        q.question_id: q for _, q in ledger.iter_family("questions") if isinstance(q, Question)
    }
    resolutions: dict[str, Resolution] = {}
    voids: dict[str, Void] = {}
    for _, r in ledger.iter_family("resolutions"):
        if isinstance(r, Resolution):
            resolutions.setdefault(r.question_id, r)
        elif isinstance(r, Void):
            voids.setdefault(r.question_id, r)
    forecasts, skips = [], []
    for _, r in ledger.iter_family("forecasts"):
        if isinstance(r, Forecast):
            forecasts.append(r)
        elif isinstance(r, Skip):
            skips.append(r)
    rec = Record(questions, resolutions, voids, forecasts, skips)
    rec.scored = scored_forecasts(rec)
    return rec


def excluded(rec: Record, qid: str) -> bool:
    """True if a question is voided for a reason that removes it from scoring."""
    v = rec.voids.get(qid)
    return v is not None and v.reason_code != "source_revised"


def scored_forecasts(rec: Record, days: Iterable[date] | None = None) -> list[Scored]:
    """Resolved, non-voided forecasts (optionally only for the given batch dates)."""
    keep = set(days) if days is not None else None
    out = []
    for f in rec.forecasts:
        q = rec.questions.get(f.question_id)
        r = rec.resolutions.get(f.question_id)
        if q is None or r is None or excluded(rec, f.question_id):
            continue
        if keep is not None and q.batch_date not in keep:
            continue
        out.append(
            Scored(
                f.question_id,
                f.forecaster_id,
                f.forecaster_version,
                q.domain,
                q.batch_date,
                f.probability,
                r.outcome,
            )
        )
    return out


@dataclass(frozen=True)
class Row:
    """One forecaster's scores."""

    forecaster_id: str
    n: int
    brier: float
    log: float
    skill: float | None  # Brier skill vs base_rate on the questions both answered
    skill_n: int


def leaderboard(scored: Sequence[Scored], reference: str = REFERENCE) -> list[Row]:
    """Scores per forecaster, best Brier first; the reference is always included if present."""
    by_f: dict[str, dict[str, Scored]] = {}
    for s in scored:
        by_f.setdefault(s.forecaster_id, {})[s.question_id] = s
    ref = by_f.get(reference, {})
    rows = []
    for fid, items in by_f.items():
        ps = [s.probability for s in items.values()]
        ys = [s.outcome for s in items.values()]
        common = [q for q in items if q in ref]
        skill = None
        if common:
            b = brier([items[q].probability for q in common], [items[q].outcome for q in common])
            b0 = brier([ref[q].probability for q in common], [ref[q].outcome for q in common])
            skill = brier_skill(b, b0)
        rows.append(Row(fid, len(items), brier(ps, ys), log_score(ps, ys), skill, len(common)))
    return sorted(rows, key=lambda r: (r.brier, r.forecaster_id))


@dataclass(frozen=True)
class Counts:
    """Record counts shown next to every leaderboard."""

    questions: int
    resolved: int
    voided: dict[str, int]
    open: int
    forecasts: int
    skips: dict[str, int]


def counts(rec: Record) -> Counts:
    """Questions, resolutions, voids by reason, open questions, forecasts, skips by reason."""
    voided = Counter(v.reason_code for v in rec.voids.values())
    closed = set(rec.resolutions) | {q for q in rec.voids if excluded(rec, q)}
    return Counts(
        questions=len(rec.questions),
        resolved=sum(1 for q in rec.resolutions if not excluded(rec, q)),
        voided=dict(sorted(voided.items())),
        open=sum(1 for q in rec.questions if q not in closed),
        forecasts=len(rec.forecasts),
        skips=dict(sorted(Counter(s.reason_code for s in rec.skips).items())),
    )


def format_table(rows: Sequence[Row]) -> str:
    """Plain-text leaderboard for the CLI."""
    lines = [f"{'forecaster':<14}{'n':>6}{'brier':>9}{'log':>9}{'skill':>9}"]
    for r in rows:
        skill = "-" if r.skill is None else f"{r.skill:+.3f}"
        lines.append(f"{r.forecaster_id:<14}{r.n:>6}{r.brier:>9.4f}{r.log:>9.4f}{skill:>9}")
    return "\n".join(lines)
