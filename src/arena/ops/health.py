"""Health checks after every job, and incident issues (SPEC 12, task T033).

Checks (each pass/fail with a one-line detail):

- `batch_sealed`: after the lock (or after a morning run), today's questions exist and the
  batch seal was written before the lock.
- `next_batch_published` (evening job only): tomorrow's questions exist (T160).
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
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, time, timedelta
from typing import Any

from arena.config import Settings
from arena.ledger import Ledger, layout
from arena.ledger.verify import verify
from arena.models import BatchSeal, Forecast, Skip
from arena.ops.jobs import EVENING_EARLIEST

LOCK = time(9, 30)
OVERDUE_AFTER = timedelta(days=5)
FRESH_WITHIN = timedelta(hours=36)
FRESH_OVERRIDES = {"markets": timedelta(hours=96)}
MAX_PARSE_FAILURE_RATE = 0.20
MIN_LLM_ANSWERS = 5
LLM_FORECASTERS = frozenset(
    {
        "llm_plain",
        "llm_context",
        "llm_local",
        "agent",
        "agent_graph",
        "llm_local_ft",
        "llm_router",
        "agent_hybrid",
        "agent_quant",
        "agent_analyst",
    }
)
INCIDENT_LABEL = "incident"
INCIDENT_TITLE = "Forecast Arena incident: a job or health check failed"
CORE_FORECASTERS = frozenset(
    {"base_rate", "persistence", "ml", "llm_plain", "llm_context", "agent"}
)


def expected_forecasters(settings: Settings) -> frozenset[str]:
    """Declared production roster, independent of what the factory actually registered."""
    return (
        CORE_FORECASTERS
        | ({"llm_local"} if settings.llm_local else set())
        | ({"agent_graph"} if settings.agent_graph else set())
        | ({"llm_local_ft"} if settings.llm_local_ft else set())
        | ({"agent_hybrid"} if settings.agent_hybrid else set())
        | ({"agent_quant"} if settings.agent_quant else set())
        | ({"agent_analyst"} if settings.agent_analyst else set())
        | ({"bandit_hedge"} if settings.bandit else set())
    )


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
            {
                "job": self.job,
                "at": self.at.isoformat(),
                "ok": self.ok,
                "checks": [asdict(c) for c in self.checks],
            },
            indent=1,
        )

    def markdown(self) -> str:
        """A short Markdown table of the checks."""
        rows = [f"| {'pass' if c.ok else 'FAIL'} | `{c.name}` | {c.detail} |" for c in self.checks]
        return "\n".join(["| Result | Check | Detail |", "|---|---|---|", *rows])


def run_checks(
    ledger: Ledger,
    job: str,
    now: datetime,
    *,
    force_fail: bool = False,
    roster: frozenset[str] = CORE_FORECASTERS,
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

    if job == "morning" and todays:  # T276: informational data contracts on the stored contexts
        from arena.ops.contracts import check_batch

        checked, bad = check_batch(ledger, rec, today)
        shown = "; ".join(bad[:3]) + (f"; and {len(bad) - 3} more" if len(bad) > 3 else "")
        rep.checks.append(
            Check(
                "data_contracts",
                True,  # informational: never fails a run or a clean day (SPEC 2.9)
                f"{checked} contexts checked, {len(bad)} violations"
                + (f": {shown}" if bad else ""),
            )
        )

    if job == "evening":  # T160: tomorrow's questions are published tonight
        nxt = today + timedelta(days=1)
        n = sum(q.batch_date == nxt for q in rec.questions.values())
        detail = f"{n} questions for {nxt}" if n else f"no questions for {nxt}"
        if not n and now.time() < EVENING_EARLIEST:
            # A manual or test run before the publishing window does nothing by design
            # (jobs.evening refuses it), so it must not fail the run for "not published yet".
            rep.checks.append(
                Check("next_batch_published", True, f"not due before {EVENING_EARLIEST:%H:%M} UTC")
            )
        else:
            rep.checks.append(Check("next_batch_published", n > 0, detail))

    overdue = sorted(
        q.question_id
        for q in rec.questions.values()
        if q.resolve_after + OVERDUE_AFTER < now
        and q.question_id not in rec.resolutions
        and q.question_id not in rec.voids
    )
    rep.checks.append(
        Check(
            "nothing_overdue",
            not overdue,
            "none" if not overdue else f"{len(overdue)} overdue, e.g. {', '.join(overdue[:3])}",
        )
    )

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
        Check(
            "sources_fresh",
            not stale,
            "stale: " + ", ".join(stale) if stale else f"{len(latest)} domain(s) fresh",
        )
    )

    todays_ids = {q.question_id for q in todays}
    if job == "morning" or now >= lock:
        records: list[Forecast | Skip] = [*rec.forecasts, *rec.skips]
        pairs = Counter(
            (r.question_id, r.forecaster_id) for r in records if r.question_id in todays_ids
        )
        bad = sorted(
            f"{qid}::{fid}" for qid in todays_ids for fid in roster if pairs[qid, fid] != 1
        )
        rep.checks.append(
            Check(
                "forecaster_coverage",
                bool(todays_ids) and not bad,
                f"expected {len(todays_ids) * len(roster)} forecast-or-skip pairs; "
                + (
                    f"missing/duplicate: {', '.join(bad[:5])}"
                    if bad
                    else "complete"
                    if todays_ids
                    else f"no batch for {today}, so nothing could be covered (see batch_sealed)"
                ),
            )
        )
        unavailable = [
            s
            for s in rec.skips
            if s.question_id in todays_ids
            and s.forecaster_id == "ml"
            and s.reason_code in {"model_missing", "error"}
        ]
        rep.checks.append(
            Check(
                "ml_available", not unavailable, f"{len(unavailable)} ML model_missing/error skips"
            )
        )
    answers = sum(
        1
        for f in rec.forecasts
        if f.forecaster_id in LLM_FORECASTERS and f.question_id in todays_ids
    )
    failures = sum(
        1
        for s in rec.skips
        if s.forecaster_id in LLM_FORECASTERS
        and s.question_id in todays_ids
        and s.reason_code == "parse_failure"
    )
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
    run(
        [
            "label",
            "create",
            INCIDENT_LABEL,
            *scope,
            "--color",
            "B60205",
            "--description",
            "A Forecast Arena job or health check failed",
            "--force",
        ]
    )
    run(
        [
            "issue",
            "create",
            *scope,
            "--title",
            INCIDENT_TITLE,
            "--label",
            INCIDENT_LABEL,
            "--body",
            body,
        ]
    )
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
    lines += [
        "",
        'See docs/RUNBOOK.md, "If something breaks". An open incident breaks the '
        "clean-day streak (SPEC 2.9).",
    ]
    return "\n".join(lines)
