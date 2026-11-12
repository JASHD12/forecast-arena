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
def score_show() -> None:
    """Print scores (built in T028)."""
    _not_yet("T028")


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


@daily.command("morning")
def daily_morning() -> None:
    """Questions, forecasts, seal, push (built in T027)."""
    _not_yet("T027")


@daily.command("resolve")
def daily_resolve() -> None:
    """Resolve, seal finished days, rescore (built in T027)."""
    _not_yet("T027")


@main.group()
def report() -> None:
    """Reports computed from the public record."""


@report.command("cv")
def report_cv() -> None:
    """Headline numbers for a CV, from the ledger only (built in T101)."""
    _not_yet("T101")


if __name__ == "__main__":
    main()
