"""`arena a2a`: cards, one question to an agent, and a local server (T362, T364).

The A2A SDK is an optional requirement (`requirements/a2a.txt`), so every import of it happens
inside a command, and a missing SDK is a clear error, not a broken `arena` CLI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import click

from arena.cli import Ctx, main

ORACLE = "arena-oracle"


def _require_sdk() -> None:
    try:
        import a2a  # noqa: F401
    except ImportError:
        click.echo("the A2A SDK is not installed: pip install -r requirements/a2a.txt", err=True)
        sys.exit(2)


def _oracle(obj: Ctx) -> Any:
    from arena.a2a.oracle import Oracle

    docs = Path("docs")
    return Oracle.from_ledger(obj.ledger, docs.parent if (docs / "SPEC.md").is_file() else None)


@main.group("a2a")
def a2a_group() -> None:
    """Agent-to-agent (A2A) agents of this project: arena-oracle and the committee members."""


@a2a_group.command("card")
@click.option(
    "--agent", default=ORACLE, show_default=True, help="arena-oracle or a committee member"
)
def card_command(agent: str) -> None:
    """Print an Agent Card as JSON."""
    _require_sdk()
    from google.protobuf.json_format import MessageToDict

    from arena.a2a.cards import build_card, validate_card
    from arena.a2a.oracle import oracle_spec
    from arena.agent.committee import AgentCommittee

    specs = {ORACLE: oracle_spec(), **AgentCommittee(None).agent_specs()}
    if agent not in specs:
        raise click.ClickException(
            f"unknown agent {agent!r}; choose from {', '.join(sorted(specs))}"
        )
    card = build_card(specs[agent], f"http://127.0.0.1:8000/{agent}/")
    if problems := validate_card(card):
        raise click.ClickException("; ".join(problems))
    click.echo(json.dumps(MessageToDict(card), indent=2, ensure_ascii=False))


@a2a_group.command("ask")
@click.option("--url", default=None, help="base URL of a running agent; default: in-process oracle")
@click.option(
    "--skill", default=None, help="list_questions, get_question, leaderboard, explain_method"
)
@click.option("--arg", "args", multiple=True, help="skill argument as key=value (repeatable)")
@click.option("--text", default=None, help="a free-text request instead of --skill")
@click.pass_obj
def ask_command(
    obj: Ctx, url: str | None, skill: str | None, args: tuple[str, ...], text: str | None
) -> None:
    """Send one request to arena-oracle and print the answer (exit 1 unless it completed)."""
    _require_sdk()
    import httpx

    from arena.a2a.client import A2AClient
    from arena.a2a.oracle import build_oracle_app
    from arena.a2a.transport import base_url, run_sync

    if not skill and not text:
        raise click.UsageError("give --skill or --text")
    kv = dict(a.split("=", 1) for a in args if "=" in a)
    payload: dict[str, Any] = {"skill": skill, "args": kv} if skill else {"text": text}

    async def go() -> Any:
        if url:
            async with httpx.AsyncClient(timeout=30.0) as http:
                return await A2AClient(ORACLE, http, url).ask(payload)
        app = build_oracle_app(_oracle(obj), f"{base_url(ORACLE)}/")
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=base_url(ORACLE)) as http:
            return await A2AClient(ORACLE, http, base_url(ORACLE)).ask(payload)

    result = run_sync(go())
    click.echo(
        json.dumps(
            {"state": result.state, "data": result.data, "error": result.error}, ensure_ascii=False
        )
    )
    if not result.ok:
        sys.exit(1)


@a2a_group.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8001, show_default=True, type=int)
@click.pass_obj
def serve_command(obj: Ctx, host: str, port: int) -> None:
    """Serve arena-oracle on localhost (development; the committee runs in-process, not served)."""
    _require_sdk()
    import uvicorn

    from arena.a2a.oracle import build_oracle_app

    uvicorn.run(build_oracle_app(_oracle(obj), f"http://{host}:{port}/"), host=host, port=port)
