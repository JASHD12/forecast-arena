"""Leaderboards (SPEC 10): common-set and all-question boards, per domain and overall.

Wording rules: with fewer than 30 official days or fewer than 300 resolved common-set
forecasts a board carries the label "too early to tell"; a difference is described as
supported only when its 95% day-block interval excludes zero. No causal claims.
Headline boards use only the official record (batches on or after the official start);
rehearsal days are excluded and counted.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date

from arena.scoring.core import REFERENCE, Scored, log_score
from arena.scoring.stats import Interval, day_block_bootstrap, paired_brier_difference

COMMON_GROUP = ("base_rate", "ml", "llm_plain", "llm_context", "agent")
ALL_GROUP = ("base_rate", "persistence", "ml", "ensemble")
MIN_DAYS = 30
MIN_COMMON = 300
TOO_EARLY = "too early to tell"


@dataclass(frozen=True)
class BoardRow:
    """One forecaster on one board."""

    forecaster_id: str
    n: int
    brier: Interval
    log: float
    vs_reference: Interval | None  # Brier difference to base_rate (negative = better)

    @property
    def verdict(self) -> str:
        """Wording for the difference to the base rate."""
        if self.vs_reference is None:
            return "reference"
        if not self.vs_reference.excludes_zero:
            return "no supported difference from base_rate"
        return (
            "supported: better than base_rate"
            if self.vs_reference.estimate < 0
            else "supported: worse than base_rate"
        )


@dataclass
class Board:
    """A leaderboard."""

    kind: str  # "common" or "all"
    domain: str  # a domain name or "overall"
    forecasters: list[str]
    questions: int
    days: int
    rows: list[BoardRow] = field(default_factory=list)
    label: str | None = None


def official(scored: Sequence[Scored], start: date | None) -> list[Scored]:
    """Only official-record forecasts (none before the official start is set)."""
    if start is None:
        return []
    return [s for s in scored if s.batch_date >= start]


def _rows(by: dict[str, dict[str, Scored]], qs: list[str]) -> list[BoardRow]:
    out = []
    ref = by.get(REFERENCE)
    for fid in sorted(by):
        items = [by[fid][q] for q in qs]
        terms = [(min(0.99, max(0.01, s.probability)) - s.outcome) ** 2 for s in items]
        bi = day_block_bootstrap([s.batch_date for s in items], terms)
        lg = log_score([s.probability for s in items], [s.outcome for s in items])
        vs = None
        if ref is not None and fid != REFERENCE:
            vs = paired_brier_difference(
                [s.batch_date for s in items],
                [s.probability for s in items],
                [ref[q].probability for q in qs],
                [s.outcome for s in items],
            )
        out.append(BoardRow(fid, len(items), bi, lg, vs))
    return sorted(out, key=lambda r: (r.brier.estimate, r.forecaster_id))


def board(
    scored: Sequence[Scored], kind: str, domain: str = "overall", official_days: int | None = None
) -> Board:
    """Build one board from (already filtered) scored forecasts."""
    group = COMMON_GROUP if kind == "common" else ALL_GROUP
    pool = [
        s
        for s in scored
        if s.forecaster_id in group and (domain == "overall" or s.domain == domain)
    ]
    by: dict[str, dict[str, Scored]] = {}
    for s in pool:
        by.setdefault(s.forecaster_id, {})[s.question_id] = s
    if kind == "common":
        active = [f for f in group if f in by]
        qs = sorted(set.intersection(*(set(by[f]) for f in active))) if active else []
        by = {f: by[f] for f in active}
    else:
        qs = sorted(set(by.get(REFERENCE, {})))
        by = {f: v for f, v in by.items() if set(qs) <= set(v)}
    b = Board(
        kind,
        domain,
        sorted(by),
        len(qs),
        len({by[REFERENCE][q].batch_date for q in qs}) if REFERENCE in by else 0,
    )
    if qs and REFERENCE in by:
        b.rows = _rows(by, qs)
    days = official_days if official_days is not None else b.days
    common_n = len(qs) * len(by) if kind == "common" else None
    if days < MIN_DAYS or (common_n is not None and common_n < MIN_COMMON) or not b.rows:
        b.label = TOO_EARLY
    return b


def all_boards(
    scored: Sequence[Scored], domains: Sequence[str], official_days: int | None = None
) -> list[Board]:
    """Common and all-question boards, overall and per domain."""
    out = []
    for kind in ("common", "all"):
        for d in ("overall", *domains):
            out.append(board(scored, kind, d, official_days))
    return out
