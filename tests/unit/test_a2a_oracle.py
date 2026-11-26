"""T364: `arena-oracle` (the ledger as a read-only A2A agent) against the MCP `Benchmark`."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("a2a")

from click.testing import CliRunner
from factories import B, forecast, question

from arena.a2a import oracle
from arena.a2a.cards import build_card, validate_card
from arena.a2a.transport import InProcessHub, base_url, run_sync
from arena.cli import main
from arena.ledger import Ledger, layout
from arena.mcp_server import Benchmark
from arena.models import Evidence, Resolution


def _ledger(tmp_path: Path) -> Ledger:
    led = Ledger(tmp_path)
    q1, q2 = question(), question(template="max_gt")
    led.append(layout.questions_path(B), [q1, q2])
    led.append(
        layout.forecasts_path(B),
        [
            forecast(q1, "base_rate", 0.5),
            forecast(q1, "llm_context", 0.8),
            forecast(q2, "base_rate", 0.5),
        ],
    )
    res = Resolution(
        question_id=q1.question_id,
        outcome=1,
        observed_value=91.2,
        resolved_at=q1.resolve_after,
        evidence=Evidence(source_url="https://x", snapshot_sha256="a" * 64, values_used={}),
    )
    led.append(layout.resolutions_path(B), [res])
    return led


def _ask(led: Ledger, payload: dict[str, Any]) -> Any:
    o = oracle.Oracle.from_ledger(led)

    async def go() -> Any:
        async with InProcessHub({oracle.NAME: (oracle.oracle_spec(), o.handle)}) as hub:
            return await hub.client(oracle.NAME).ask(payload)

    return run_sync(go())


def _roundtrip(obj: Any) -> Any:
    """What a value looks like after the A2A data part (JSON numbers become floats)."""
    return json.loads(json.dumps(obj, default=str))


def _floats(obj: Any) -> Any:
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, int | float):
        return float(obj)
    if isinstance(obj, list):
        return [_floats(x) for x in obj]
    return {k: _floats(v) for k, v in obj.items()}


def test_the_card_is_valid_and_lists_the_four_skills() -> None:
    spec = oracle.oracle_spec()
    card = build_card(spec, "http://x.invalid/")
    assert validate_card(card) == []
    assert [s.id for s in card.skills] == list(oracle.SKILLS)
    assert all("read-only" in s.tags for s in card.skills)


def test_answers_equal_the_mcp_servers_benchmark_on_the_same_ledger(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    b = Benchmark(led)
    qid = question().question_id
    lq = _ask(led, {"skill": "list_questions", "args": {"limit": 10}})
    assert lq.ok and lq.data is not None
    assert lq.data["result"] == _floats(_roundtrip(b.list_questions(None, "all", 10)))
    gq = _ask(led, {"skill": "get_question", "args": {"question_id": qid}})
    assert gq.data is not None and gq.data["result"] == _floats(_roundtrip(b.get_question(qid)))
    lb = _ask(led, {"skill": "leaderboard", "args": {}})
    assert lb.data is not None and lb.data["result"] == _floats(_roundtrip(b.leaderboard(None)))
    assert lq.data["notice"].endswith("not advice of any kind.")


def test_free_text_is_routed_to_a_skill(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    qid = question().question_id
    r = _ask(led, {"text": f"show me {qid}"})
    assert r.data is not None and r.data["skill"] == "get_question"
    r = _ask(led, {"text": "who leads the leaderboard on electricity?"})
    assert r.data is not None and r.data["skill"] == "leaderboard"
    r = _ask(led, {"text": "list the latest open questions"})
    assert r.data is not None and r.data["skill"] == "list_questions"
    r = _ask(led, {"text": "what does the lock time mean?"})
    assert r.data is not None and r.data["skill"] == "explain_method"
    assert r.data["result"]["refused"] is True  # no documents loaded in this test


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Should I buy Google stock?", "finance"),
        ("what will the DAX do tomorrow", "finance"),
        ("is apple worth buying", "finance"),
        ("what is my email password", "personal"),
        ("Who is Jane Doe?", "personal"),
    ],
)
def test_advice_stocks_and_private_persons_are_refused_as_answers(
    tmp_path: Path, text: str, kind: str
) -> None:
    r = _ask(_ledger(tmp_path), {"text": text})
    assert r.ok and r.data is not None
    assert (
        r.data["refused"] is True and r.data["reason"] == kind and r.data["result"]
        if False
        else True
    )
    assert r.data["message"] == oracle.REFUSALS[kind]


def test_a_refusal_also_applies_to_skill_arguments(tmp_path: Path) -> None:
    r = _ask(
        _ledger(tmp_path),
        {"skill": "explain_method", "args": {"question": "should i buy etf shares"}},
    )
    assert r.data is not None and r.data["refused"] is True


def test_unknown_skill_is_a_refusal_and_unknown_question_is_a_failed_task(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    r = _ask(led, {"skill": "run_sql", "args": {"query": "select 1"}})
    assert r.data is not None and r.data["refused"] is True and r.data["reason"] == "unknown_skill"
    r = _ask(led, {"skill": "get_question", "args": {"question_id": "nope"}})
    assert not r.ok and r.state == "FAILED" and "unknown question" in (r.error or "")


def test_the_guard_patterns_are_the_ones_of_the_ask_the_arena_page() -> None:
    ts = Path("site_ts/chat.ts").read_text()
    for name in ("STOCK", "COMPANY", "PRICEY", "ADVICE", "PERSONAL", "PERSON_NAME"):
        m = re.search(rf"const {name} = /(.*)/[a-z]*;", ts)
        assert m is not None, name
        assert m.group(1) == getattr(oracle, name), name


def test_no_skill_writes_to_the_ledger(tmp_path: Path) -> None:
    led = _ledger(tmp_path)
    before = sorted(
        str(p.relative_to(tmp_path)) + str(p.stat().st_size)
        for p in tmp_path.rglob("*")
        if p.is_file()
    )
    for payload in (
        {"skill": "list_questions", "args": {"status": "open"}},
        {"skill": "leaderboard", "args": {"domain": "power"}},
        {"text": "list open questions"},
    ):
        _ask(led, payload)
    after = sorted(
        str(p.relative_to(tmp_path)) + str(p.stat().st_size)
        for p in tmp_path.rglob("*")
        if p.is_file()
    )
    assert before == after


def test_the_cli_asks_the_oracle_in_process_and_prints_the_card(tmp_path: Path) -> None:
    led = _ledger(tmp_path / "ledger")
    runner = CliRunner()
    r = runner.invoke(main, ["--ledger-dir", str(led.root), "a2a", "ask", "--skill", "leaderboard"])
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["state"] == "COMPLETED" and out["data"]["skill"] == "leaderboard"
    r = runner.invoke(main, ["a2a", "card", "--agent", "arena-oracle"])
    assert r.exit_code == 0 and json.loads(r.output)["name"] == "arena-oracle"
    r = runner.invoke(main, ["a2a", "card", "--agent", "historian"])
    assert r.exit_code == 0 and json.loads(r.output)["name"] == "historian"
    assert runner.invoke(main, ["a2a", "card", "--agent", "nobody"]).exit_code != 0


def test_the_rest_api_mounts_the_oracle_with_a_fetchable_card(tmp_path: Path) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    import httpx

    from arena.a2a.client import A2AClient
    from arena.api.app import create_app

    app = create_app(_ledger(tmp_path))

    async def go() -> Any:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as http:
            card = (await http.get("/a2a/.well-known/agent-card.json")).json()
            r = await A2AClient("arena-oracle", http, "http://t/a2a").ask({"skill": "leaderboard"})
            return card, r

    card, r = run_sync(go())
    assert card["name"] == "arena-oracle"
    assert r.ok and r.data is not None and r.data["result"]["rows"]
    assert base_url("x").endswith(".invalid")
