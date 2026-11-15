"""Commands for the public record: ledger verification and seals, health checks, and the
official start."""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import click

from arena.cli import (
    Ctx,
    _push,
    _sync,
    health,
    ledger,
    official,
)


@health.command("check")
@click.option(
    "--job", required=True, type=click.Choice(["evening", "morning", "resolve", "weekly"])
)
@click.option(
    "--report",
    "report_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Also write the report as JSON here.",
)
@click.option("--force-fail", is_flag=True, help="Add a failing check (dry-run tests only).")
@click.option("--record", is_flag=True, help="Also write the report to the ledger (health/).")
@click.pass_obj
def health_check(
    obj: Ctx, job: str, report_path: Path | None, force_fail: bool, record: bool
) -> None:
    """Run the health checks against the ledger; exit 1 if any fails."""
    from arena.ops.health import expected_forecasters, run_checks
    from arena.ops.official import record_health

    now = obj.clock.now()
    rep = run_checks(
        obj.ledger, job, now, force_fail=force_fail, roster=expected_forecasters(obj.settings)
    )
    payload = json.loads(rep.to_json())
    payload["workflow_run_id"] = os.environ.get("GITHUB_RUN_ID")
    payload["workflow_attempt"] = os.environ.get("GITHUB_RUN_ATTEMPT")
    report_json = json.dumps(payload, indent=1)
    click.echo(rep.markdown())
    if report_path is not None:
        report_path.write_text(report_json, encoding="utf-8")
    if record:
        click.echo(f"recorded: {record_health(obj.ledger, report_json, job, now.date())}")
    sys.exit(0 if rep.ok else 1)


@health.command("execution")
@click.option(
    "--job",
    required=True,
    type=click.Choice(["morning", "evening", "resolve", "weekly", "players"]),
)
@click.option("--push", is_flag=True)
@click.pass_obj
def health_execution(obj: Ctx, job: str, push: bool) -> None:
    """Publish executed-code identity before the live application setup starts."""
    from arena.ledger.manifest import code_sha
    from arena.ops.health import expected_forecasters
    from arena.ops.workflow_evidence import record_execution

    if obj.dry_run:
        return
    remote = _sync(obj, push)
    now = obj.clock.now()
    data = {
        "workflow_run_id": os.environ["GITHUB_RUN_ID"],
        "workflow_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "job": job,
        "intended_date": now.date().isoformat(),
        "started_at": now.isoformat(),
        "code_sha": code_sha(),
        "event_sha": os.environ.get("GITHUB_SHA"),
        "roster": sorted(expected_forecasters(obj.settings)),
    }
    click.echo(record_execution(obj.ledger, data, now))
    _push(obj, remote, "execution", now.date())


@health.command("audit-workflows")
@click.option("--repo", required=True, help="GitHub repository owner/name.")
@click.option("--days", default=1, type=click.IntRange(1, 30), show_default=True)
@click.option("--include-created-at", default=None, help="Also reconcile the triggering run's day.")
@click.option("--push", is_flag=True)
@click.pass_obj
def health_audit_workflows(
    obj: Ctx, repo: str, days: int, include_created_at: str | None, push: bool
) -> None:
    """Persist complete workflow outcomes; API/permission errors never mean success."""
    from arena.ops.workflow_evidence import collect_audit, save_audit

    if obj.dry_run:
        raise click.UsageError("workflow auditing requires durable evidence; omit --dry-run")
    remote = _sync(obj, push)
    now = obj.clock.now()
    targets: set[date] = {now.date() - timedelta(days=i) for i in range(1, days + 1)}
    if include_created_at:
        target = datetime.fromisoformat(include_created_at.replace("Z", "+00:00")).date()
        if target < now.date():
            targets.add(target)
    for day in sorted(targets):
        audit = collect_audit(
            obj.ledger, repo, day, now, players_required=bool(obj.settings.players_csv_url)
        )
        click.echo(save_audit(obj.ledger, audit))
    _push(obj, remote, "workflow_audit", now.date())


@official.command("update")
@click.option("--push", is_flag=True, help="Commit and push the ledger afterwards.")
@click.pass_obj
def official_update(obj: Ctx, push: bool) -> None:
    """Evaluate the clean-day rule; write meta/official_start.json once when due."""
    from arena.ops.official import update_official_start

    now = obj.clock.now()
    dec = update_official_start(obj.ledger, now, obj.settings.official_start_not_before)
    for st in dec.statuses[-7:]:
        click.echo(f"{st.day}: {'clean' if st.clean else '; '.join(st.reasons)}")
    click.echo(dec.summary())
    if push and obj.settings.ledger_remote and not obj.dry_run:
        _push(obj, obj.settings.ledger_remote, "health", now.date())


@health.command("incident")
@click.option("--report", "report_path", type=click.Path(path_type=Path), required=True)
@click.option("--job-status", required=True, help="The workflow's job status.")
@click.option("--run-url", required=True)
@click.option("--repo", default=None, help="owner/name (default: the current repository).")
def health_incident(report_path: Path, job_status: str, run_url: str, repo: str | None) -> None:
    """Open, update or close the single `incident` issue (needs `gh` and a token)."""
    import json as _json

    from arena.ops.health import incident_body, sync_incident

    report = _json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
    healthy = job_status == "success" and report is not None and bool(report.get("ok"))
    click.echo(sync_incident(healthy, incident_body(report, job_status, run_url), repo=repo))


@ledger.command("verify")
@click.option("--git", "with_git", is_flag=True, help="Also check commit times from history.")
@click.pass_obj
def ledger_verify(obj: Ctx, with_git: bool) -> None:
    """Recompute seals and the chain; check every forecast precedes its lock."""
    from arena.ledger.verify import verify

    rep = verify(obj.ledger)
    if with_git:
        from arena.ledger.gitcheck import verify_git

        rep.errors.extend(verify_git(obj.ledger))
    click.echo(rep.summary())
    sys.exit(0 if rep.ok else 1)


@ledger.command("seal-batch")
@click.pass_obj
def ledger_seal_batch(obj: Ctx) -> None:
    """Write the batch seal for --date (idempotent)."""
    from arena.ledger.seal import seal_batch

    if obj.dry_run:
        click.echo(f"dry run: would seal batch {obj.day}")
        return
    seal = seal_batch(obj.ledger, obj.day, obj.clock)
    click.echo(f"batch {seal.batch_date} sealed: {len(seal.files)} files")


@ledger.command("seal-days")
@click.pass_obj
def ledger_seal_days(obj: Ctx) -> None:
    """Seal every finished, unsealed day in order (idempotent)."""
    from arena.ledger.seal import seal_pending_days

    if obj.dry_run:
        click.echo("dry run: would seal pending days")
        return
    for seal in seal_pending_days(obj.ledger, obj.clock):
        click.echo(f"day {seal.day} sealed: chain {seal.chain_sha256[:12]}")
