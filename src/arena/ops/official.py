"""Pre-registered official start (SPEC principle 2.9; tasks T035 and T110).

A ledger day is *clean* when all of these hold for it:

- a real (not dry-run) morning run succeeded;
- no real run failed;
- at least one health report was recorded and every recorded report passed (a failed
  report is exactly what opens the `incident` issue, so this also means "no incident");
- the day is sealed into the hash chain.

The official record starts on the day after the first run of `STREAK` consecutive clean
days, and never before the owner's `not_before` date (T110: the roadmap's model and timing
changes must be live first). The date is written once to `meta/official_start.json` when
it takes effect and is never changed or rewritten.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from arena.ledger import Ledger, layout
from arena.models import RunManifest

STREAK = 5


@dataclass
class DayStatus:
    """Why a day is or is not clean."""

    day: date
    reasons: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        """True when nothing disqualifies the day."""
        return not self.reasons


def record_health(ledger: Ledger, report_json: str, job: str, day: date) -> str:
    """Write a health report to `health/` (numbered per job and day); returns its path."""
    n = 1
    while ledger.exists(layout.health_path(day, job, n)):
        n += 1
    rel = layout.health_path(day, job, n)
    ledger.write_raw(rel, (report_json.rstrip("\n") + "\n").encode())
    return rel


def _by_day(ledger: Ledger, folder: str) -> dict[date, list[str]]:
    out: dict[date, list[str]] = {}
    for rel in ledger.list_files(folder):
        d = layout.day_of(rel)
        if d is not None:
            out.setdefault(d, []).append(rel)
    return out


def day_statuses(ledger: Ledger, first: date, last: date) -> list[DayStatus]:
    """Clean-day status of every day from `first` to `last`."""
    runs = _by_day(ledger, "runs")
    health = _by_day(ledger, "health")
    out = []
    d = first
    while d <= last:
        st = DayStatus(d)
        manifests = [m for rel in runs.get(d, []) if isinstance(m := ledger.read_json(rel),
                                                                   RunManifest)]  # fmt: skip
        real = [m for m in manifests if not m.dry_run]
        if not any(m.job == "morning" and m.status == "ok" for m in real):
            st.reasons.append("no successful morning run")
        failed = [m.run_id for m in real if m.status == "failed"]
        if failed:
            st.reasons.append(f"failed run(s): {', '.join(failed)}")
        reports = [json.loads(ledger.read_bytes(rel)) for rel in sorted(health.get(d, []))]
        if not reports:
            st.reasons.append("no health report recorded")
        elif not all(r.get("ok") for r in reports):
            st.reasons.append("a health check failed (incident)")
        if not ledger.exists(layout.day_seal_path(d)):
            st.reasons.append("day not sealed")
        out.append(st)
        d += timedelta(days=1)
    return out


def rule_start(statuses: list[DayStatus]) -> date | None:
    """The day after the first run of STREAK consecutive clean days, if any."""
    run = 0
    for st in statuses:
        run = run + 1 if st.clean else 0
        if run == STREAK:
            return st.day + timedelta(days=1)
    return None


@dataclass
class StartDecision:
    """What the official-start check found."""

    existing: str | None
    streak: int
    rule: date | None
    start: date | None
    written: bool = False
    statuses: list[DayStatus] = field(default_factory=list)

    def summary(self) -> str:
        """One line for logs and the Status page."""
        if self.existing:
            return f"official start {self.existing} (fixed)"
        if self.start and self.written:
            return f"official start written: {self.start}"
        if self.rule:
            return f"rule met (start {self.rule}); waiting for the not-before date ({self.start})"
        return f"rehearsal: {self.streak} clean day(s) in a row, {STREAK} needed"


def first_day(ledger: Ledger) -> date | None:
    """The first ledger day with questions (the start of the rehearsal)."""
    days = [d for rel in ledger.list_files("questions") if (d := layout.day_of(rel))]
    return min(days) if days else None


def update_official_start(
    ledger: Ledger, now: datetime, not_before: date | None = None, *, write: bool = True
) -> StartDecision:
    """Evaluate the rule on completed days and write the start date once, when due
    (`write=False`: evaluate only, e.g. for the site)."""
    today = now.date()
    if ledger.exists(layout.OFFICIAL_START_PATH):
        data = json.loads(ledger.read_bytes(layout.OFFICIAL_START_PATH))
        return StartDecision(str(data.get("official_start")), 0, None, None)
    first = first_day(ledger)
    if first is None or first > today - timedelta(days=1):
        return StartDecision(None, 0, None, None)
    statuses = day_statuses(ledger, first, today - timedelta(days=1))
    streak = 0
    for st in reversed(statuses):
        if not st.clean:
            break
        streak += 1
    rule = rule_start(statuses)
    start = None if rule is None else max(rule, not_before) if not_before else rule
    dec = StartDecision(None, streak, rule, start, statuses=statuses)
    if write and start is not None and today >= start:
        payload: dict[str, Any] = {
            "official_start": start.isoformat(),
            "rule_start": rule.isoformat() if rule else None,
            "not_before": not_before.isoformat() if not_before else None,
            "decided_at": now.isoformat(),
            "clean_days": [s.day.isoformat() for s in statuses if s.clean],
            "rule": f"day after the first {STREAK} consecutive clean days (SPEC 2.9)",
        }
        ledger.write_raw(
            layout.OFFICIAL_START_PATH, (json.dumps(payload, indent=1) + "\n").encode()
        )
        dec.written = True
    return dec
