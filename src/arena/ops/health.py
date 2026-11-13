"""Health checks after every job, and incident issues (SPEC 12, task T033).

Checks (each pass/fail with a one-line detail):

- `batch_sealed`: after the lock (or after a morning run), today's questions exist and the
  batch seal was written before the lock.
- `nothing_overdue`: no question is still unresolved and unvoided more than
  `OVERDUE_AFTER` past its `resolve_after` (longer than every domain's grace period).
- `sources_fresh`: every domain that asked questions in the last week asked some within
  36 hours (96 for markets, whose source publishes on working days only).
- `parse_failures`: under 20% of today's LLM answers failed the output contract.
- `ledger_verify`: `ledger verify` passes.

Alerts: a failed job or failed check opens one GitHub issue labelled `incident` (or
comments on the open one; deduplicated by title); a healthy run closes it. The issue
commands go through the `gh` CLI with the workflow token (standing approval 5); the runner
is injectable so tests never touch GitHub.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Any

from arena.ledger import Ledger, layout
from arena.ledger.verify import verify
from arena.models import BatchSeal

LOCK = time(9, 30)
OVERDUE_AFTER = timedelta(days=5)
FRESH_WITHIN = timedelta(hours=36)
FRESH_OVERRIDES = {"markets": timedelta(hours=96)}
MAX_PARSE_FAILURE_RATE = 0.20
MIN_LLM_ANSWERS = 5
LLM_FORECASTERS = frozenset({"llm_plain", "llm_context", "llm_local", "agent", "agent_graph"})
INCIDENT_LABEL = "incident"
INCIDENT_TITLE = "Forecast Arena incident: a job or health check failed"


@dataclass(frozen=True)
class Check:
    """One health check result."""

    name: str
    ok: bool
    detail: str


@dataclass
class HealthReport:
    """All checks of one run."""

    job: str
    at: datetime
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when every check passed."""
        return all(c.ok for c in self.checks)

    def failed(self) -> list[Check]:
        """The failed checks."""
        return [c for c in self.checks if not c.ok]

    def to_json(self) -> str:
        """Serialised report (for the workflow step and the incident text)."""
        return json.dumps(
            {"job": self.job, "at": self.at.isoformat(), "ok": self.ok,
             "checks": [asdict(c) for c in self.checks]}, indent=1)  # fmt: skip

    def markdown(self) -> str:
        """A short Markdown table of the checks."""
        rows = [f"| {'pass' if c.ok else 'FAIL'} | `{c.name}` | {c.detail} |" for c in self.checks]
        return "\n".join(["| Result | Check | Detail |", "|---|---|---|", *rows])


def run_checks(
    ledger: Ledger, job: str, now: datetime, *, force_fail: bool = False
) -> HealthReport:
    """Run every health check against the ledger at `now` (UTC)."""
    from arena.scoring.core import load

    rep = HealthReport(job, now)
    rec = load(ledger)
    today = now.date()
    lock = datetime.combine(today, LOCK, tzinfo=UTC)

    todays = [q for q in rec.questions.values() if q.batch_date == today]
    seal_rel = layout.batch_seal_path(today)
    seal = ledger.read_json(seal_rel) if ledger.exists(seal_rel) else None
    if now < lock and job != "morning":
        rep.checks.append(Check("batch_sealed", True, "not due before the 09:30 UTC lock"))
    elif not todays:
        rep.checks.append(Check("batch_sealed", False, f"no questions for {today}"))
    elif not isinstance(seal, BatchSeal):
        rep.checks.append(Check("batch_sealed", False, f"no batch seal for {today}"))
    elif seal.sealed_at > lock:
        rep.checks.append(
            Check("batch_sealed", False, f"sealed at {seal.sealed_at:%H:%M} UTC, after the lock")
        )
    else:
        rep.checks.append(
            Check(
                "batch_sealed",
                True,
                f"{len(todays)} questions sealed at {seal.sealed_at:%H:%M} UTC",
            )
        )

    overdue = sorted(
        q.question_id
        for q in rec.questions.values()
        if q.resolve_after + OVERDUE_AFTER < now
        and q.question_id not in rec.resolutions
        and q.question_id not in rec.voids
    )
    rep.checks.append(
        Check("nothing_overdue", not overdue,
              "none" if not overdue else f"{len(overdue)} overdue, e.g. {', '.join(overdue[:3])}")
    )  # fmt: skip

    week_ago = today - timedelta(days=7)
    latest: dict[str, datetime] = {}
    for q in rec.questions.values():
        if q.batch_date >= week_ago:
            latest[q.domain] = max(latest.get(q.domain, q.created_at), q.created_at)
    stale = [
        f"{d} (last {t:%Y-%m-%d %H:%M})"
        for d, t in sorted(latest.items())
        if now - t > FRESH_OVERRIDES.get(d, FRESH_WITHIN)
    ]
    rep.checks.append(
        Check("sources_fresh", not stale,
              "stale: " + ", ".join(stale) if stale else f"{len(latest)} domain(s) fresh")
    )  # fmt: skip

    todays_ids = {q.question_id for q in todays}
    answers = sum(
        1 for f in rec.forecasts
        if f.forecaster_id in LLM_FORECASTERS and f.question_id in todays_ids
    )  # fmt: skip
    failures = sum(
        1 for s in rec.skips
        if s.forecaster_id in LLM_FORECASTERS and s.question_id in todays_ids
        and s.reason_code == "parse_failure"
    )  # fmt: skip
    total = answers + failures
    rate = failures / total if total else 0.0
    ok = total < MIN_LLM_ANSWERS or rate < MAX_PARSE_FAILURE_RATE
    rep.checks.append(
        Check("parse_failures", ok, f"{failures} of {total} LLM answers unparseable ({rate:.0%})")
    )

    v = verify(ledger)
    rep.checks.append(Check("ledger_verify", v.ok, v.summary()))
    if force_fail:
        rep.checks.append(Check("forced_failure", False, "deliberate failure (dry-run test)"))
    return rep


Runner = Callable[[Sequence[str]], str]


def gh_runner(args: Sequence[str]) -> str:
    """Run `gh` and return stdout (raises on failure)."""
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def sync_incident(
    healthy: bool, body: str, *, run: Runner = gh_runner, repo: str | None = None
) -> str:
    """Open/comment/close the single incident issue. Returns what was done."""
    scope = ["--repo", repo] if repo else []
    found = json.loads(
        run(
            [
                "issue",
                "list",
                *scope,
                "--label",
                INCIDENT_LABEL,
                "--state",
                "open",
                "--json",
                "number,title",
                "--limit",
                "50",
            ]
        )
        or "[]"
    )
    open_ids = [str(i["number"]) for i in found if i.get("title") == INCIDENT_TITLE]
    if healthy:
        for n in open_ids:
            run(["issue", "comment", n, *scope, "--body", "Healthy again.\n\n" + body])
            run(["issue", "close", n, *scope])
        return f"closed {', '.join(open_ids)}" if open_ids else "healthy, nothing open"
    if open_ids:
        run(["issue", "comment", open_ids[0], *scope, "--body", body])
        return f"commented on {open_ids[0]}"
    run(["label", "create", INCIDENT_LABEL, *scope, "--color", "B60205",
         "--description", "A Forecast Arena job or health check failed", "--force"])  # fmt: skip
    run(["issue", "create", *scope, "--title", INCIDENT_TITLE, "--label", INCIDENT_LABEL,
         "--body", body])  # fmt: skip
    return "opened"


def incident_body(report: dict[str, Any] | None, job_status: str, run_url: str) -> str:
    """Issue text from a health report (may be missing when the job crashed early)."""
    lines = [f"Job status: **{job_status}**. Run: {run_url}", ""]
    if report is None:
        lines.append("No health report was produced (the job failed before the check).")
    else:
        lines += ["| Result | Check | Detail |", "|---|---|---|"]
        for c in report.get("checks", []):
            res = "pass" if c["ok"] else "FAIL"
            lines.append(f"| {res} | `{c['name']}` | {c['detail']} |")
    lines += ["", "See docs/RUNBOOK.md, \"If something breaks\". An open incident breaks the "
              "clean-day streak (SPEC 2.9)."]  # fmt: skip
    return "\n".join(lines)
