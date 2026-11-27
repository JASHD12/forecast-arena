"""Leaderboards (SPEC 10): common-set and all-question boards, per domain and overall.

Wording rules: with fewer than 30 official days or fewer than 300 resolved common-set
forecasts a board carries the label "too early to tell"; a difference is described as
supported only when its 95% day-block interval excludes zero. No causal claims.
Headline boards use only the official record (batches on or after the official start);
rehearsal days are excluded and counted.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from arena.scoring.core import REFERENCE, Scored, log_score
from arena.scoring.stats import Interval, day_block_bootstrap, paired_brier_difference

#: The headline comparison group. `llm_plain` ("AI, question only") was a member until it was
#: retired on 2026-11-27 (owner decision: cost, and keep only the agents with data); its forecasts
#: stay in the ledger, but it writes no new ones, so it cannot be required of new questions.
COMMON_GROUP = ("base_rate", "ml", "llm_context", "agent")
ALL_GROUP = ("base_rate", "persistence", "ml", "ensemble")
MIN_DAYS = 30
MIN_COMMON = 300
TOO_EARLY = "too early to tell"
SETTLING_DAYS = 30


def settling_rule(all_scored: Sequence[Scored], start: date | None) -> Callable[[Scored], bool]:
    """True for forecasts of a topic added after the official start, in its first 30 days.

    Such a topic has its own board from day one, but stays out of the overall boards until it has
    30 days of results, so adding a topic never changes the headline that was already running
    (conservative reading of SPEC 10 and I8; DECISIONS 2026-11-22). Topics that were live before
    the official start are never settling. `all_scored` is the whole scored record, rehearsal days
    included, so the first day of a topic is found correctly."""
    first: dict[str, date] = {}
    for s in all_scored:
        if s.domain not in first or s.batch_date < first[s.domain]:
            first[s.domain] = s.batch_date

    def settling(s: Scored) -> bool:
        if start is None:
            return False
        f = first.get(s.domain)
        return f is not None and f > start and s.batch_date < f + timedelta(days=SETTLING_DAYS)

    return settling


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
    missing_forecasters: list[str] = field(default_factory=list)


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
    scored: Sequence[Scored],
    kind: str,
    domain: str = "overall",
    official_days: int | None = None,
    settling: Callable[[Scored], bool] | None = None,
) -> Board:
    """Build one board from (already filtered) scored forecasts.

    `settling` (see `settling_rule`) removes new topics from the overall boards only."""
    group = COMMON_GROUP if kind == "common" else ALL_GROUP
    pool = [
        s
        for s in scored
        if s.forecaster_id in group
        and (domain == "overall" or s.domain == domain)
        and not (domain == "overall" and settling is not None and settling(s))
    ]
    by: dict[str, dict[str, Scored]] = {}
    for s in pool:
        by.setdefault(s.forecaster_id, {})[s.question_id] = s
    missing = []
    if kind == "common":
        missing = [f for f in group if f not in by]
        # The registered group is fixed even when a member has no scored forecasts.
        # An empty member makes the common set empty, rather than changing its meaning.
        by = {f: by.get(f, {}) for f in group}
        qs = sorted(set.intersection(*(set(by[f]) for f in group)))
    else:
        qs = sorted(set(by.get(REFERENCE, {})))
        by = {f: v for f, v in by.items() if set(qs) <= set(v)}
    b = Board(
        kind,
        domain,
        sorted(by),
        len(qs),
        len({by[REFERENCE][q].batch_date for q in qs}) if REFERENCE in by else 0,
        missing_forecasters=missing,
    )
    if qs and REFERENCE in by:
        b.rows = _rows(by, qs)
    days = official_days if official_days is not None else b.days
    common_n = len(qs) * len(by) if kind == "common" else None
    if days < MIN_DAYS or (common_n is not None and common_n < MIN_COMMON) or not b.rows:
        b.label = TOO_EARLY
    return b


def all_boards(
    scored: Sequence[Scored],
    domains: Sequence[str],
    official_days: int | None = None,
    settling: Callable[[Scored], bool] | None = None,
) -> list[Board]:
    """Common and all-question boards, overall and per domain."""
    out = []
    for kind in ("common", "all"):
        for d in ("overall", *domains):
            out.append(board(scored, kind, d, official_days, settling))
    return out
