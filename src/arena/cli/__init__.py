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
from arena.ledger import Ledger


@dataclass
class Ctx:
    """Shared state handed to every command."""

    settings: Settings
    ledger: Ledger
    day: date
    dry_run: bool
    clock: Clock


def _not_yet(task: str) -> None:
    click.echo(f"not implemented yet (see {task} in docs/project/TASKS.md)", err=True)
    sys.exit(2)


@click.group()
@click.option(
    "--ledger-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Ledger checkout (default: ARENA_LEDGER_DIR or ./_ledger).",
)
@click.option(
    "--date",
    "day",
    type=click.DateTime(["%Y-%m-%d"]),
    default=None,
    help="Batch or target date (UTC). Default: today.",
)
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


@main.group()
def health() -> None:
    """Health checks after every job and the incident issue (SPEC 12)."""


@main.group()
def official() -> None:
    """The pre-registered official start (SPEC 2.9)."""


# ----- questions -----------------------------------------------------------------------
@main.group()
def questions() -> None:
    """Generate and list questions."""


# ----- data ----------------------------------------------------------------------------
@main.group()
def data() -> None:
    """Fetch and cache source data (git-ignored cache, ARENA_CACHE_DIR)."""


# ----- the other groups ----------------------------------------------------------------
@main.group()
def forecast() -> None:
    """Run forecasters."""


@main.group()
def resolve() -> None:
    """Resolve questions whose answers are available."""


@main.group()
def score() -> None:
    """Compute scores from the ledger."""


@main.group()
def site() -> None:
    """Build the static site."""


@main.group()
def daily() -> None:
    """The scheduled jobs."""


def _sync(obj: Ctx, push: bool) -> str | None:
    """Check out the ledger branch when pushing; returns the remote to push to.

    A dry run with --push still checks the branch out (so it sees the real state) but
    returns None: nothing is pushed, and the job itself works on a throwaway copy."""
    if not push:
        return None
    from arena.ledger.gitsync import ensure_checkout

    remote = obj.settings.ledger_remote
    if not remote:
        raise click.UsageError("--push needs ARENA_LEDGER_REMOTE")
    click.echo(f"ledger checkout: {ensure_checkout(remote, obj.ledger.root)}")
    return None if obj.dry_run else remote


def _push(obj: Ctx, remote: str | None, job: str, day: date) -> None:
    if remote is None:
        return
    from arena.ledger.gitsync import commit_and_push

    sha = commit_and_push(obj.ledger.root, job, day)
    click.echo(f"ledger pushed: {sha}" if sha else "ledger: nothing to push")


@main.group()
def schedule() -> None:
    """Gate for scheduled runs, which GitHub can start hours late (T180)."""


@main.group()
def weekly() -> None:
    """The weekly job: retrain, compare, promote by rule."""


@main.group()
def report() -> None:
    """Reports computed from the public record."""


# ----- llm -----------------------------------------------------------------------------
@main.group()
def llm() -> None:
    """Checks of the configured LLM provider."""


@main.group("eval")
def eval_group() -> None:
    """LLM evaluation on a frozen golden set (T124; never part of the live record)."""


@main.command("api")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.pass_obj
def api_command(obj: Ctx, host: str, port: int) -> None:
    """Serve the ledger read-only over HTTP (FastAPI; OpenAPI docs at /docs)."""
    import uvicorn

    from arena.api.app import create_app

    uvicorn.run(create_app(obj.ledger), host=host, port=port)


@main.command("mcp")
@click.pass_obj
def mcp_command(obj: Ctx) -> None:
    """Serve the ledger read-only over MCP on stdio (needs requirements/mcp.txt)."""
    from arena.mcp_server import build_server

    build_server(obj.ledger).run("stdio")


# Command modules register themselves on the groups above (T187: split by purpose).
from arena.cli import jobs, llm_cmds, record, reports  # noqa: E402,F401
