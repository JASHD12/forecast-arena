"""Durable workflow evidence, including failures before setup and after deployment.

The observer uses GitHub's complete, paginated run/attempt/job inventory. It stores
snapshots on the *observation* day, so late evidence never mutates a sealed work day.
Missing inventories, pending attempts, unknown modes and missing execution/health
evidence fail closed. Successful retries cannot erase a failed attempt.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from arena.ledger import Ledger
from arena.models import UTCDatetime
from arena.ops.health import gh_runner

WORKFLOWS = frozenset({"morning", "evening", "resolve", "weekly", "players"})
Api = Callable[[str], list[Any]]


class Attempt(BaseModel):
    """One Actions attempt, including its final deployment and smoke-test stages."""

    model_config = ConfigDict(extra="forbid")
    key: str
    job: str
    event: str
    created_at: UTCDatetime
    started_at: UTCDatetime | None = None
    ended_at: UTCDatetime | None = None
    intended_date: date | None = None
    mode: Literal["live", "dry-run", "unknown"]
    conclusion: str | None
    no_op: bool = False
    code_sha: str | None = None
    event_sha: str
    stages: dict[str, str | None] = Field(default_factory=dict)
    health: dict[str, Any] | None = None


class Audit(BaseModel):
    """A complete API observation for one work day; immutable once written."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    target_day: date
    observed_at: UTCDatetime
    inventory_complete: bool
    expected_attempts: list[str]
    attempts: list[Attempt]
    incident_numbers: list[int]
    open_incident_numbers: list[int]
    players_required: bool = False


def gh_api(endpoint: str) -> list[Any]:
    """GET every page; never accept a truncated single page as complete evidence."""
    pages: list[Any] = json.loads(
        gh_runner(["api", "--method", "GET", endpoint, "--paginate", "--slurp"])
    )
    return pages


def _items(pages: list[Any], field: str | None = None) -> list[dict[str, Any]]:
    out = [x for page in pages for x in (page[field] if field else page)]
    if field and pages and len(out) < int(pages[0].get("total_count", len(out))):
        raise ValueError(f"incomplete GitHub {field} pagination")
    return out


def _stamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _evidence(ledger: Ledger, prefix: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in ledger.list_files(prefix):
        data = json.loads(ledger.read_bytes(path))
        if data.get("workflow_run_id") and data.get("workflow_attempt"):
            key = f"{data['workflow_run_id']}:{data['workflow_attempt']}"
            if prefix == "health" and key in out:
                data["ok"] = out[key].get("ok") is True and data.get("ok") is True
                data["checks"] = [*out[key].get("checks", []), *data.get("checks", [])]
            out[key] = data
    return out


def record_execution(ledger: Ledger, data: dict[str, Any], now: datetime) -> str:
    """Persist application identity before constructing sources or models."""
    run_id, attempt = int(data["workflow_run_id"]), int(data["workflow_attempt"])
    path = f"workflow_executions/{now:%Y/%m/%d}/{run_id}-{attempt}.json"
    if not ledger.exists(path):
        ledger.write_raw(path, (json.dumps(data, sort_keys=True) + "\n").encode())
    return path


def collect_audit(
    ledger: Ledger,
    repo: str,
    day: date,
    now: datetime,
    *,
    api: Api = gh_api,
    players_required: bool = False,
) -> Audit:
    """Inspect all operational run attempts and incidents for a completed UTC day.

    API failures abort collection: they never produce an inventory_complete=True file.
    Reopened issues are conservatively considered incident days from creation through
    their latest close; this can delay readiness, but cannot conceal an open incident.
    """
    if day >= now.date():
        raise ValueError("only completed UTC days can be audited")
    base = f"repos/{repo}"
    start = datetime.combine(day, time(), UTC)
    end = datetime.combine(day + timedelta(days=1), time(), UTC)
    # Unfiltered pagination also discovers reruns of old runs. Filtering by created
    # would miss them and applies GitHub's 1,000-result search limit.
    runs = _items(api(f"{base}/actions/runs?per_page=100"), "workflow_runs")
    identities, health = _evidence(ledger, "workflow_executions"), _evidence(ledger, "health")
    attempts: list[Attempt] = []
    for run in runs:
        job = str(run.get("path", "")).split("/")[-1].removesuffix(".yml")
        if job not in WORKFLOWS:
            continue
        if (
            run.get("status") == "completed"
            and run.get("updated_at")
            and _stamp(run["updated_at"]) < start
        ):
            continue
        for number in range(1, int(run["run_attempt"]) + 1):
            key = f"{run['id']}:{number}"
            # All attempts, including failures preceding a later successful rerun.
            detail = api(f"{base}/actions/runs/{run['id']}/attempts/{number}")[0]
            ident = identities.get(key, {})
            started = _stamp(detail.get("run_started_at") or detail["created_at"])
            ended = _stamp(detail["updated_at"]) if detail.get("status") == "completed" else now
            if not (started < end and ended >= start) and ident.get("intended_date") != str(day):
                continue
            jobs = _items(
                api(f"{base}/actions/runs/{run['id']}/attempts/{number}/jobs?per_page=100"), "jobs"
            )
            stages = {
                f"{j['name']} / {s['name']}": s.get("conclusion")
                for j in jobs
                for s in j.get("steps", [])
            }
            stages.update({f"job: {j['name']}": j.get("conclusion") for j in jobs})
            no_op = (
                detail["event"] == "schedule"
                and any(j["name"] == "gate" and j.get("conclusion") == "success" for j in jobs)
                and any(j["name"] == "run" and j.get("conclusion") == "skipped" for j in jobs)
                and detail.get("conclusion") == "success"
            )
            title = str(detail.get("display_title", ""))
            mode: Literal["live", "dry-run", "unknown"] = "unknown"
            if detail["event"] == "schedule" or title == f"{job} / live":
                mode = "live"
            elif title == f"{job} / dry-run":
                mode = "dry-run"
            attempts.append(
                Attempt(
                    key=key,
                    job=job,
                    event=detail["event"],
                    created_at=detail["created_at"],
                    started_at=detail.get("run_started_at"),
                    ended_at=detail.get("updated_at")
                    if detail.get("status") == "completed"
                    else None,
                    intended_date=ident.get("intended_date"),
                    mode=mode,
                    conclusion=detail.get("conclusion"),
                    no_op=no_op,
                    code_sha=ident.get("code_sha"),
                    event_sha=detail["head_sha"],
                    stages=stages,
                    health=health.get(key),
                )
            )
    issues = _items(api(f"{base}/issues?state=all&labels=incident&per_page=100"))
    start, end = (
        datetime.combine(day, time(), UTC),
        datetime.combine(day + timedelta(days=1), time(), UTC),
    )
    incidents = [
        int(i["number"])
        for i in issues
        if not i.get("pull_request")
        and _stamp(i["created_at"]) < end
        and (i.get("closed_at") is None or _stamp(i["closed_at"]) >= start)
    ]
    opened = [
        int(i["number"]) for i in issues if i.get("state") == "open" and not i.get("pull_request")
    ]
    return Audit(
        target_day=day,
        observed_at=now,
        inventory_complete=True,
        expected_attempts=[a.key for a in attempts],
        attempts=attempts,
        incident_numbers=incidents,
        open_incident_numbers=opened,
        players_required=players_required,
    )


def save_audit(ledger: Ledger, audit: Audit) -> str:
    """Append on the observation day; never touch the already sealed target day."""
    prefix = f"workflow_audits/{audit.observed_at:%Y/%m/%d}/{audit.target_day}"
    number = 1
    while ledger.exists(f"{prefix}-{number}.json"):
        number += 1
    path = f"{prefix}-{number}.json"
    ledger.write_raw(path, (audit.model_dump_json(indent=1) + "\n").encode())
    return path


def audits(ledger: Ledger) -> list[Audit]:
    """Read validated observations; corrupt evidence is an error, never clean evidence."""
    return sorted(
        (
            Audit.model_validate_json(ledger.read_bytes(p))
            for p in ledger.list_files("workflow_audits")
        ),
        key=lambda a: a.observed_at,
    )


def audit_reasons(audit: Audit) -> list[str]:
    """Fail-closed readiness for the complete inventory, not just application manifests."""
    reasons = []
    keys = [a.key for a in audit.attempts]
    if (
        not audit.inventory_complete
        or len(set(keys)) != len(keys)
        or set(keys) != set(audit.expected_attempts)
        or audit.observed_at.date() <= audit.target_day
    ):
        reasons.append("incomplete workflow inventory")
    fulfilled = set()
    for a in audit.attempts:
        if a.mode == "dry-run":
            continue
        if a.mode == "unknown":
            reasons.append(f"unknown workflow mode: {a.key}")
        bad = [
            name
            for name, result in a.stages.items()
            if result not in {"success", "skipped", "neutral"}
        ]
        if a.conclusion != "success" or bad or a.ended_at is None:
            reasons.append(f"workflow failed or unfinished: {a.key} ({', '.join(bad)})")
            continue
        if a.no_op:
            continue
        if a.code_sha in {None, "unknown", ""} or a.intended_date is None or not a.stages:
            reasons.append(f"missing workflow execution evidence: {a.key}")
            continue
        if a.job != "players" and (a.health is None or a.health.get("ok") is not True):
            reasons.append(f"missing or failed workflow health: {a.key}")
            continue
        if a.job == "morning" and not any(
            c.get("name") == "forecaster_coverage" and c.get("ok") is True
            for c in (a.health or {}).get("checks", [])
        ):
            reasons.append(f"missing roster health: {a.key}")
            continue
        if a.mode == "live" and a.intended_date == audit.target_day:
            fulfilled.add(a.job)
    required = {"morning", "evening", "resolve"}
    if audit.target_day.weekday() == 6:
        required.add("weekly")
    if audit.players_required:
        required.add("players")
    if missing := required - fulfilled:
        reasons.append("missing completed workflow work: " + ", ".join(sorted(missing)))
    if audit.incident_numbers:
        reasons.append("incident open during day: " + ", ".join(map(str, audit.incident_numbers)))
    return reasons


def workflow_day_reasons(observations: list[Audit], day: date) -> list[str]:
    """Latest inventory plus any earlier definite failures, never erased by retries."""
    matches = [a for a in observations if a.target_day == day]
    if not matches:
        return ["no complete workflow outcome evidence"]
    reasons = audit_reasons(matches[-1])
    failed = {
        a.key
        for audit in matches
        for a in audit.attempts
        if a.mode != "dry-run" and a.conclusion not in {None, "success"}
    }
    if failed:
        reasons.append("failed workflow attempt(s): " + ", ".join(sorted(failed)))
    return reasons
