"""Commands for the scheduled jobs (evening, players, morning, resolve, weekly), the
schedule gate, and lower-level job steps."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import click

from arena.cli import (
    Ctx,
    _not_yet,
    _push,
    _sync,
    daily,
    data,
    forecast,
    questions,
    resolve,
    schedule,
    score,
    weekly,
)
from arena.ledger import layout
from arena.models import Question


@questions.command("list")
@click.pass_obj
def questions_list(obj: Ctx) -> None:
    """List the questions of the batch --date."""
    for rec in obj.ledger.read(layout.questions_path(obj.day)):
        if isinstance(rec, Question):
            click.echo(f"{rec.question_id}\t{rec.text}")


@questions.command("generate")
def questions_generate() -> None:
    """Generate questions for --date (built in T024/T027)."""
    _not_yet("T027")


@data.command("backfill")
@click.option(
    "--series",
    "keys",
    multiple=True,
    default=["price_de_lu"],
    show_default=True,
    help="SMARD series key(s) to backfill.",
)
@click.pass_obj
def data_backfill(obj: Ctx, keys: tuple[str, ...]) -> None:
    """Fetch the full SMARD history into the cache and print a summary."""
    from arena.domains.power_history import backfill
    from arena.sources.http import HttpClient
    from arena.sources.smard import SmardClient

    client = SmardClient(HttpClient(obj.settings.user_agent()), cache_dir=obj.settings.cache_dir)
    for key in keys:
        click.echo(backfill(client, key, until=obj.clock.now()).line())


@forecast.command("run")
def forecast_run() -> None:
    """Run all forecasters for the batch --date (built in T027)."""
    _not_yet("T027")


@resolve.command("run")
def resolve_run() -> None:
    """Resolve whatever is resolvable now (built in T027)."""
    _not_yet("T027")


@score.command("show")
@click.pass_obj
def score_show(obj: Ctx) -> None:
    """Print the leaderboard and record counts computed from the ledger."""
    from arena.scoring.core import counts, format_table, leaderboard, load

    rec = load(obj.ledger)
    c = counts(rec)
    click.echo(format_table(leaderboard(rec.scored)))
    click.echo(
        f"questions={c.questions} resolved={c.resolved} open={c.open} "
        f"voided={c.voided} forecasts={c.forecasts} skips={c.skips}"
    )


@schedule.command("due")
@click.option("--job", required=True, type=click.Choice(["evening", "morning", "players"]))
@click.option("--sync", is_flag=True, help="Check out the ledger branch first (in Actions).")
@click.pass_obj
def schedule_due(obj: Ctx, job: str, sync: bool) -> None:
    """Print whether JOB has work to do now; write `due=true|false` to $GITHUB_OUTPUT."""
    import os

    from arena.ops.schedule import is_due

    if sync:
        remote = obj.settings.ledger_remote
        if not remote:
            raise click.UsageError("--sync needs ARENA_LEDGER_REMOTE")
        from arena.ledger.gitsync import ensure_checkout

        ensure_checkout(remote, obj.ledger.root)
    d = is_due(job, obj.clock.now(), obj.ledger)
    click.echo(f"{job}: {'due' if d.due else 'not due'} ({d.reason})")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"due={'true' if d.due else 'false'}\n")


@daily.command("evening")
@click.option("--push", is_flag=True, help="Sync with and push to the ledger branch.")
@click.pass_obj
def daily_evening(obj: Ctx, push: bool) -> None:
    """Publish tomorrow's questions tonight (T160): the batch is the day after --date.

    No forecasts are written; the morning job answers them before the usual lock.
    """
    from arena.ops.jobs import evening
    from arena.ops.wiring import build_domains

    batch = obj.day + timedelta(days=1)
    remote = _sync(obj, push)
    domains = build_domains(obj.settings, obj.clock.now(), job="evening", ledger=obj.ledger)
    result = evening(obj.ledger, batch, obj.clock, domains, dry_run=obj.dry_run)
    click.echo(result.line())
    for w in result.warnings:
        click.echo(f"warning: {w}")
    _push(obj, remote, "evening", batch)


@daily.command("players")
@click.option("--push", is_flag=True, help="Sync with and push to the ledger branch.")
@click.pass_obj
def daily_players(obj: Ctx, push: bool) -> None:
    """Public players' forecasts for --date from the form CSV, before the lock (T161)."""
    from arena.forecasters.players import parse_players_csv
    from arena.ops.jobs import players
    from arena.sources.http import HttpClient

    remote = _sync(obj, push)
    intake = None
    url = obj.settings.players_csv_url
    if url:
        body = HttpClient(obj.settings.user_agent()).get(url).body
        intake = parse_players_csv(body.decode("utf-8-sig"))
    result = players(obj.ledger, obj.day, obj.clock, intake, dry_run=obj.dry_run)
    click.echo(result.line())
    for w in result.warnings:
        click.echo(f"warning: {w}")
    _push(obj, remote, "players", obj.day)


@daily.command("morning")
@click.option("--push", is_flag=True, help="Sync with and push to the ledger branch.")
@click.pass_obj
def daily_morning(obj: Ctx, push: bool) -> None:
    """Questions, forecasts, snapshot and batch seal for --date (idempotent)."""
    from arena.ops.jobs import morning
    from arena.ops.wiring import build_domains, build_forecasters

    remote = _sync(obj, push)
    domains = build_domains(obj.settings, obj.clock.now(), ledger=obj.ledger)
    forecasters, guard = build_forecasters(
        obj.ledger, domains, obj.settings, obj.day, dry_run=obj.dry_run, clock=obj.clock
    )

    def attach(rec: object) -> None:
        if guard is not None:
            guard.recorder = rec  # type: ignore[assignment]

    result = morning(
        obj.ledger, obj.day, obj.clock, domains, forecasters, dry_run=obj.dry_run, on_record=attach
    )
    click.echo(result.line())
    for w in result.warnings:
        click.echo(f"warning: {w}")
    _push(obj, remote, "morning", obj.day)


@daily.command("resolve")
@click.option("--push", is_flag=True, help="Sync with and push to the ledger branch.")
@click.pass_obj
def daily_resolve(obj: Ctx, push: bool) -> None:
    """Resolve what is resolvable now, record revisions, seal finished days."""
    from arena.ops.jobs import resolve
    from arena.ops.wiring import build_domains

    remote = _sync(obj, push)
    now = obj.clock.now()
    domains = build_domains(obj.settings, now, job="resolve", ledger=obj.ledger)
    result = resolve(obj.ledger, obj.clock, domains, dry_run=obj.dry_run)
    click.echo(result.line())
    for w in result.warnings:
        click.echo(f"warning: {w}")
    _push(obj, remote, "resolve", now.date())


@weekly.command("run")
@click.option("--push", is_flag=True, help="Sync with and push to the ledger branch.")
@click.option("--domain", "only", multiple=True, help="Limit to these domains.")
@click.pass_obj
def weekly_run(obj: Ctx, push: bool, only: tuple[str, ...]) -> None:
    """Retrain the power and attention models and promote them by the documented rule."""
    from arena.ops.weekly import weekly as run_weekly
    from arena.ops.wiring import weekly_setup

    remote = _sync(obj, push)
    domains, trainers, cards = weekly_setup(obj.settings, obj.clock.now(), only)
    res = run_weekly(
        obj.ledger,
        obj.clock,
        domains,
        trainers,
        cards=cards,
        dry_run=obj.dry_run,
        mlruns=Path("mlruns"),
    )
    for line in res.lines():
        click.echo(line)
    _push(obj, remote, "weekly", obj.clock.now().date())
