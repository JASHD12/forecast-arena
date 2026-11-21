"""Operational panels for the Status page (T080): missed days, LLM usage, parse failures
and source freshness. Everything is computed from the ledger alone."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from arena.ledger import Ledger, layout
from arena.ledger.manifest import manifests_for_day
from arena.llm.budget import usage_from_manifests
from arena.ops.jobs import LOCK
from arena.ops.official import first_day
from arena.scoring.core import Record

#: Forecasters that call an LLM and can therefore fail to parse.
LLM_FORECASTERS = (
    "llm_plain",
    "llm_context",
    "llm_local",
    "agent",
    "agent_graph",
    "llm_local_ft",
    "llm_router",
    "agent_hybrid",
)


def missed_days(ledger: Ledger, today: date) -> list[date]:
    """Batch days from the first ledger day up to yesterday that have no batch seal
    (no forecasts were locked in for them)."""
    first = first_day(ledger)
    out: list[date] = []
    if first is None:
        return out
    d = first
    while d < today:
        if not ledger.exists(layout.batch_seal_path(d)):
            out.append(d)
        d += timedelta(days=1)
    return out


@dataclass(frozen=True)
class UsageDay:
    """LLM usage summed over every real run of one UTC day."""

    day: date
    requests: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    reserved_tokens: int = 0
    unreported_requests: int = 0

    @property
    def total(self) -> int:
        """All reported and conservatively reserved tokens counted by the guard."""
        return self.input_tokens + self.output_tokens + self.cached_tokens + self.reserved_tokens


def llm_usage(ledger: Ledger, today: date, days: int = 7) -> list[UsageDay]:
    """Usage per day for the last `days` days (newest first), from the run manifests."""
    out = []
    for i in range(days):
        d = today - timedelta(days=i)
        u = usage_from_manifests(ledger, d)
        out.append(
            UsageDay(
                d,
                u.requests,
                u.input_tokens,
                u.output_tokens,
                u.cache_read_tokens + u.cache_write_tokens,
                u.reserved_tokens,
                u.unreported_requests,
            )
        )
    return out


@dataclass(frozen=True)
class ParseRow:
    """How often one LLM forecaster produced a usable probability."""

    forecaster_id: str
    forecasts: int
    parse_failures: int
    other_skips: int

    @property
    def failure_rate(self) -> float | None:
        """Parse failures as a share of attempts (forecasts + parse failures)."""
        n = self.forecasts + self.parse_failures
        return self.parse_failures / n if n else None


def parse_failures(rec: Record) -> list[ParseRow]:
    """Per LLM forecaster: forecasts, parse failures and other skips (not `not_sampled`)."""
    fc = Counter(f.forecaster_id for f in rec.forecasts)
    pf = Counter(s.forecaster_id for s in rec.skips if s.reason_code == "parse_failure")
    other = Counter(
        s.forecaster_id for s in rec.skips if s.reason_code not in ("parse_failure", "not_sampled")
    )
    ids = [f for f in LLM_FORECASTERS if fc[f] or pf[f] or other[f]]
    return [ParseRow(f, fc[f], pf[f], other[f]) for f in ids]


@dataclass(frozen=True)
class Freshness:
    """When each domain last produced questions and resolutions."""

    domain: str
    last_batch: date
    last_resolved_at: datetime | None
    overdue: int

    def stale(self, now: datetime) -> bool:
        """True when the domain had no batch in the last two days."""
        return (now.date() - self.last_batch).days > 1


def source_freshness(rec: Record, now: datetime) -> list[Freshness]:
    """Per domain: latest batch, latest resolution time and the number of questions past
    `resolve_after` by more than a day that are still neither resolved nor void."""
    out = []
    for dom in sorted({q.domain for q in rec.questions.values()}):
        qs = [q for q in rec.questions.values() if q.domain == dom]
        res = [
            rec.resolutions[q.question_id].resolved_at
            for q in qs
            if q.question_id in rec.resolutions
        ]
        overdue = sum(
            1
            for q in qs
            if q.question_id not in rec.resolutions
            and q.question_id not in rec.voids
            and now - q.resolve_after > timedelta(days=1)
        )
        out.append(Freshness(dom, max(q.batch_date for q in qs), max(res, default=None), overdue))
    return out


#: First scheduled slot of each job's day (UTC), from the workflows' cron lines (T180).
FIRST_SLOT = {"morning": time(0, 15), "evening": time(16, 0), "resolve": time(0, 30)}


@dataclass(frozen=True)
class StartRow:
    """When the first real run of a job started on one UTC day."""

    day: date
    job: str
    started: datetime
    late_by: timedelta  # since the day's first scheduled slot
    after_lock: bool | None  # morning only: started at or after that day's lock


def run_start_times(ledger: Ledger, today: date, days: int = 7) -> list[StartRow]:
    """For each of the last `days` days and each scheduled job, the first real (not dry)
    run's start, relative to the job's first scheduled slot of the day. GitHub can start
    scheduled runs hours late; the exact slot a run belongs to is not recorded, so this
    measures the delay from the day's FIRST slot (the largest delay a run could have)."""
    rows: list[StartRow] = []
    for i in range(days):
        d = today - timedelta(days=i)
        real = [m for m in manifests_for_day(ledger, d) if not m.dry_run]
        for job, slot in FIRST_SLOT.items():
            runs = sorted((m for m in real if m.job == job), key=lambda m: m.started_at)
            if not runs:
                continue
            first = runs[0].started_at
            nominal = datetime.combine(d, slot, tzinfo=first.tzinfo)
            lock = datetime.combine(d, LOCK, tzinfo=first.tzinfo)
            rows.append(
                StartRow(d, job, first, max(first - nominal, timedelta(0)),
                         first >= lock if job == "morning" else None)
            )  # fmt: skip
    return rows


@dataclass(frozen=True)
class PlayersState:
    """What the players' intake did last (T205): computed from the run manifests only."""

    state: str  # never_ran | not_configured | late | refused | nothing | wrote
    text: str
    last_run: datetime | None = None


def players_state(ledger: Ledger, today: date, days: int = 14) -> PlayersState:
    """Say honestly whether the public players' intake is working.

    It writes forecasts only when a CSV is configured (H15) and the run starts between 08:30
    UTC and the lock; GitHub's scheduler often starts the cron later than that, so the
    last real run's own warnings decide the wording, never the configuration alone."""
    real = [
        m
        for i in range(days)
        for m in manifests_for_day(ledger, today - timedelta(days=i))
        if m.job == "players" and not m.dry_run
    ]
    if not real:
        return PlayersState(
            "never_ran",
            f"The players' intake has not run in the last {days} days. It needs the players' "
            "form (not set up yet) and a start between 08:30 UTC and the 09:30 UTC lock.",
        )
    last = max(real, key=lambda m: m.started_at)
    warns = " ".join(last.warnings)
    if "no players CSV configured" in warns:
        state, text = "not_configured", "The players' form is not set up yet."
    elif "late run" in warns or "lock passed" in warns:
        state, text = (
            "late",
            "The last intake run started after the lock, so it wrote nothing. GitHub starts "
            "scheduled runs late; until a reliable external trigger is in place the "
            "intake effectively runs only when started by hand.",
        )
    elif "refused" in warns:
        state, text = "refused", "The last intake run was refused (wrong batch date)."
    elif last.counts.get("players", 0) or last.counts.get("forecasts", 0):
        state, text = "wrote", "The last intake run wrote the players' forecasts."
    else:
        state, text = "nothing", "The last intake run found nothing to write."
    return PlayersState(state, text, last.started_at)
