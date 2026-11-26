"""T362: the A2A layer, offline (in-process ASGI transport, no socket)."""

import asyncio
import contextvars
from typing import Any

import pytest

pytest.importorskip("a2a")

from a2a.types import a2a_pb2 as pb

from arena import a2a
from arena.a2a.cards import AgentSpec, SkillSpec, build_card, skills_of, validate_card
from arena.a2a.server import payload_of
from arena.a2a.transport import InProcessHub, run_sync

SPEC = AgentSpec("echo", "Echoes its request.", "echo-r1", (SkillSpec("echo", "Echo", "Echoes."),))
VAR: contextvars.ContextVar[str] = contextvars.ContextVar("var", default="unset")


async def _echo(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("boom"):
        raise ValueError("bang")
    if payload.get("slow"):
        await asyncio.sleep(5)
    return {"echo": payload, "var": VAR.get()}


def _run(payload: dict[str, Any], *, server_timeout: float = 30.0, client_timeout: float = 30.0):
    async def go():
        agents = {"echo": (SPEC, _echo)}
        async with InProcessHub(
            agents, server_timeout=server_timeout, client_timeout=client_timeout
        ) as hub:
            return await hub.client("echo").ask(payload)

    return run_sync(go())


def test_card_is_valid_and_carries_the_disclaimer_and_protocol() -> None:
    card = build_card(SPEC, "http://x.invalid/")
    assert validate_card(card) == []
    assert a2a.DISCLAIMER in card.description
    assert skills_of(card) == ["echo"]
    (iface,) = card.supported_interfaces
    assert (iface.protocol_binding, iface.protocol_version) == ("JSONRPC", a2a.PROTOCOL_VERSION)


def test_validate_card_reports_problems() -> None:
    bad = pb.AgentCard(name="x", version="1", description="no disclaimer")
    problems = validate_card(bad)
    assert any("disclaimer" in p for p in problems)
    assert any("no supported interface" in p for p in problems)
    assert any("no skills" in p for p in problems)
    secured = build_card(SPEC, "http://x.invalid/")
    secured.security_requirements.add()
    assert any("security scheme" in p for p in validate_card(secured))


def test_the_card_is_served_at_the_well_known_path_through_the_sdk_client() -> None:
    async def go():
        async with InProcessHub({"echo": (SPEC, _echo)}) as hub:
            return await hub.client("echo").card()

    card = run_sync(go())
    assert card.name == "echo" and validate_card(card) == []


def test_a_completed_task_returns_the_data_artifact_and_a_compact_trace() -> None:
    r = _run({"a": 1, "text": "ä"})
    assert r.ok and r.state == "COMPLETED" and r.error is None
    assert r.data is not None and r.data["echo"]["text"] == "ä"
    t = r.trace()
    assert set(t) == {"agent", "state", "duration_ms", "bytes_out", "bytes_in", "error"}
    assert t["bytes_out"] > 0 and t["bytes_in"] > 0 and "ä" not in str(t)


def test_a_handler_exception_becomes_a_failed_task_with_the_error_text() -> None:
    r = _run({"boom": True})
    assert not r.ok and r.state == "FAILED" and r.data is None
    assert r.error is not None and "ValueError: bang" in r.error


def test_a_slow_handler_fails_by_the_server_timeout() -> None:
    r = _run({"slow": True}, server_timeout=0.2)
    assert not r.ok and r.state == "FAILED" and "timeout" in (r.error or "")


def test_a_slow_call_fails_by_the_client_timeout_without_raising() -> None:
    r = _run({"slow": True}, server_timeout=30.0, client_timeout=0.2)
    assert not r.ok and r.state == "ERROR" and "timeout" in (r.error or "")


def test_run_sync_carries_context_variables_and_works_inside_a_running_loop() -> None:
    VAR.set("scoped")
    assert _run({}).data["var"] == "scoped"  # type: ignore[index]

    async def inside_a_loop():
        return _run({})  # run_sync from code that already runs in an event loop

    out = asyncio.run(inside_a_loop())
    assert out.ok and out.data is not None and out.data["var"] == "scoped"


def test_unknown_agent_is_a_key_error_not_a_network_call() -> None:
    async def go():
        async with InProcessHub({"echo": (SPEC, _echo)}) as hub:
            return hub.client("nobody")

    with pytest.raises(KeyError):
        run_sync(go())


def test_payload_of_reads_json_text_data_parts_and_plain_text() -> None:
    from a2a.helpers.proto_helpers import new_data_part, new_message, new_text_part

    m = new_message([new_text_part('{"a": 1}')], role=pb.ROLE_USER)
    assert payload_of(m) == {"a": 1}
    m = new_message([new_data_part({"b": 2})], role=pb.ROLE_USER)
    assert payload_of(m) == {"b": 2.0}
    m = new_message([new_text_part("hello")], role=pb.ROLE_USER)
    assert payload_of(m) == {"text": "hello"}
    m = new_message([new_text_part("{not json")], role=pb.ROLE_USER)
    assert payload_of(m) == {"text": "{not json"}


def test_sdk_version_is_the_pinned_one() -> None:
    from pathlib import Path

    pins = Path("requirements/a2a.txt").read_text()
    assert f"a2a-sdk=={a2a.sdk_version()}" in pins
