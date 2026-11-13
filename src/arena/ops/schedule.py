"""Is a scheduled job due? (T180)

GitHub starts scheduled workflows late, sometimes by many hours (on 2026-11-13 the 05:30
UTC morning run started at 13:18, after the 09:30 lock). The jobs are idempotent, so each
is scheduled many times and a small gate decides from the clock and the ledger whether a
run has anything to do. The first on-time run does the work; the others stop at the gate
and write nothing (no run manifest, no health report, no deploy).

The gate never decides what a job writes: the job itself still enforces every rule (the
lock, the evening window, idempotency). A wrong "due" only costs a run that writes
nothing; a wrong "not due" is avoided by keeping the conditions simple.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from arena.ledger import Ledger, layout
from arena.ops.jobs import EVENING_EARLIEST, LOCK

#: Public players' forecasts are written only shortly before the lock, because a written
#: forecast is never replaced and players should have as long as possible (T161).
PLAYERS_EARLIEST = time(8, 30)

JOBS = ("evening", "morning", "players")


@dataclass(frozen=True)
class Due:
    """The gate's answer: `due` and a one-line reason for the log."""

    due: bool
    reason: str


def is_due(job: str, now: datetime, ledger: Ledger) -> Due:
    """Whether `job` has work to do at `now` (UTC)."""
    now = now.astimezone(UTC)
    today = now.date()
    lock = datetime.combine(today, LOCK, tzinfo=UTC)
    if job == "morning":
        if ledger.exists(layout.batch_seal_path(today)):
            return Due(False, f"batch {today} already sealed")
        if now >= lock:
            return Due(False, f"after the {LOCK:%H:%M} UTC lock; nothing can be written")
        return Due(True, f"batch {today} not sealed and the lock is ahead")
    if job == "evening":
        batch = today + timedelta(days=1)
        if now.time() < EVENING_EARLIEST:
            return Due(False, f"before {EVENING_EARLIEST:%H:%M} UTC")
        if ledger.exists(layout.questions_path(batch)):
            return Due(False, f"questions for {batch} already published")
        return Due(True, f"no questions for {batch} yet")
    if job == "players":
        if now.time() < PLAYERS_EARLIEST:
            return Due(False, f"before {PLAYERS_EARLIEST:%H:%M} UTC")
        if now >= lock:
            return Due(False, f"after the {LOCK:%H:%M} UTC lock")
        return Due(True, "inside the players' window before the lock")
    raise ValueError(f"unknown job {job!r}; expected one of {', '.join(JOBS)}")
