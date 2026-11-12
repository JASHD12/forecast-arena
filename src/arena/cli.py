"""`arena` command-line interface.

Common options go before the group: `arena --ledger-dir _ledger --date 2026-11-12 ledger verify`.
Commands whose task is not built yet say so and exit with status 2.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import click

from arena.clock import Clock, SystemClock
from arena.config import Settings
from arena.ledger import Ledger, layout
from arena.models import Question


@dataclass
class Ctx:
    """Shared state handed to every command."""

    settings: Settings
    ledger: Ledger
    day: date
    dry_run: bool
    clock: Clock


def _not_yet(task: str) -> None:
    click.echo(f"not implemented yet (see {task} in TASKS.md)", err=True)
    sys.exit(2)


@click.group()
@click.option("--ledger-dir", type=click.Path(path_type=Path), default=None,
              help="Ledger checkout (default: ARENA_LEDGER_DIR or ./_ledger).")  # fmt: skip
@click.option("--date", "day", type=click.DateTime(["%Y-%m-%d"]), default=None,
              help="Batch or target date (UTC). Default: today.")  # fmt: skip
@click.option("--dry-run", is_flag=True, help="Do everything except write or push.")
@click.version_option(package_name="forecast-arena")
@click.pass_context
def main(ctx: click.Context, ledger_dir: Path | None, day: object, dry_run: bool) -> None:
    """Forecast Arena: questions, forecasts, resolutions, scores and the public site."""
    settings = Settings.from_env()
    clock = SystemClock()
    the_day = day.date() if day is not None else clock.now().date()  # type: ignore[attr-defined]
    ctx.obj = Ctx(
        settings=settings,
        ledger=Ledger(ledger_dir or settings.ledger_dir),
        day=the_day,
        dry_run=dry_run,
        clock=clock,
    )


# ----- ledger --------------------------------------------------------------------------
@main.group()
def ledger() -> None:
    """Inspect, seal and verify the append-only ledger."""


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


# ----- questions -----------------------------------------------------------------------
@main.group()
def questions() -> None:
    """Generate and list questions."""


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


# ----- data ----------------------------------------------------------------------------
@main.group()
def data() -> None:
    """Fetch and cache source data (git-ignored cache, ARENA_CACHE_DIR)."""


@data.command("backfill")
@click.option("--series", "keys", multiple=True, default=["price_de_lu"], show_default=True,
              help="SMARD series key(s) to backfill.")  # fmt: skip
@click.pass_obj
def data_backfill(obj: Ctx, keys: tuple[str, ...]) -> None:
    """Fetch the full SMARD history into the cache and print a summary."""
    from arena.domains.power_history import backfill
    from arena.sources.http import HttpClient
    from arena.sources.smard import SmardClient

    client = SmardClient(HttpClient(obj.settings.user_agent()), cache_dir=obj.settings.cache_dir)
    for key in keys:
        click.echo(backfill(client, key, until=obj.clock.now()).line())


# ----- the other groups ----------------------------------------------------------------
@main.group()
def forecast() -> None:
    """Run forecasters."""


@forecast.command("run")
def forecast_run() -> None:
    """Run all forecasters for the batch --date (built in T027)."""
    _not_yet("T027")


@main.group()
def resolve() -> None:
    """Resolve questions whose answers are available."""


@resolve.command("run")
def resolve_run() -> None:
    """Resolve whatever is resolvable now (built in T027)."""
    _not_yet("T027")


@main.group()
def score() -> None:
    """Compute scores from the ledger."""


@score.command("show")
@click.pass_obj
def score_show(obj: Ctx) -> None:
    """Print the leaderboard and record counts computed from the ledger."""
    from arena.scoring.core import counts, format_table, leaderboard, load

    rec = load(obj.ledger)
    c = counts(rec)
    click.echo(format_table(leaderboard(rec.scored)))
    click.echo(f"questions={c.questions} resolved={c.resolved} open={c.open} "
               f"voided={c.voided} forecasts={c.forecasts} skips={c.skips}")  # fmt: skip


@main.group()
def site() -> None:
    """Build the static site."""


@site.command("build")
def site_build() -> None:
    """Build `site/` from the ledger (built in T029)."""
    _not_yet("T029")


@main.group()
def daily() -> None:
    """The scheduled jobs."""


def _sync(obj: Ctx, push: bool) -> str | None:
    """Check out the ledger branch when pushing; returns the remote used."""
    if not push or obj.dry_run:
        return None
    from arena.ledger.gitsync import ensure_checkout

    remote = obj.settings.ledger_remote
    if not remote:
        raise click.UsageError("--push needs ARENA_LEDGER_REMOTE")
    click.echo(f"ledger checkout: {ensure_checkout(remote, obj.ledger.root)}")
    return remote


def _push(obj: Ctx, remote: str | None, job: str, day: date) -> None:
    if remote is None:
        return
    from arena.ledger.gitsync import commit_and_push

    sha = commit_and_push(obj.ledger.root, job, day)
    click.echo(f"ledger pushed: {sha}" if sha else "ledger: nothing to push")


@daily.command("morning")
@click.option("--push", is_flag=True, help="Sync with and push to the ledger branch.")
@click.pass_obj
def daily_morning(obj: Ctx, push: bool) -> None:
    """Questions, forecasts, snapshot and batch seal for --date (idempotent)."""
    from arena.ops.jobs import morning
    from arena.ops.wiring import build_domains, build_forecasters

    remote = _sync(obj, push)
    domains = build_domains(obj.settings, obj.clock.now())
    result = morning(obj.ledger, obj.day, obj.clock, domains,
                     build_forecasters(obj.ledger, domains), dry_run=obj.dry_run)  # fmt: skip
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
    result = resolve(obj.ledger, obj.clock, build_domains(obj.settings, now),
                     dry_run=obj.dry_run)  # fmt: skip
    click.echo(result.line())
    for w in result.warnings:
        click.echo(f"warning: {w}")
    _push(obj, remote, "resolve", now.date())


@main.group()
def report() -> None:
    """Reports computed from the public record."""


@report.command("cv")
def report_cv() -> None:
    """Headline numbers for a CV, from the ledger only (built in T101)."""
    _not_yet("T101")


if __name__ == "__main__":
    main()
