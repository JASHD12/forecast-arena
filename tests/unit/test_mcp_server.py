"""`arena mcp` (T125): the read-only MCP server, through the official SDK's client."""

import asyncio
import json
import os
import sys

import pytest

pytest.importorskip("mcp")

from factories import B, forecast, question
from mcp import Client, StdioServerParameters

from arena.ledger import Ledger, layout
from arena.mcp_server import Benchmark, SqlRefused, build_server, check_sql
from arena.models import Evidence, Resolution


def _ledger(tmp_path) -> Ledger:
    led = Ledger(tmp_path)
    q1, q2 = question(), question(template="max_gt")
    led.append(layout.questions_path(B), [q1, q2])
    led.append(layout.forecasts_path(B), [forecast(q1, "base_rate", 0.5),
                                          forecast(q1, "llm_context", 0.8),
                                          forecast(q2, "base_rate", 0.5)])  # fmt: skip
    res = Resolution(question_id=q1.question_id, outcome=1, observed_value=91.2,
                     resolved_at=q1.resolve_after,
                     evidence=Evidence(source_url="https://x", snapshot_sha256="a" * 64,
                                       values_used={}))  # fmt: skip
    led.append(layout.resolutions_path(B), [res])
    return led


def call(server, name, args=None):
    async def go():
        async with Client(server) as c:
            return await c.call_tool(name, args or {})

    return asyncio.run(go())


def test_tools_are_listed_read_only(tmp_path) -> None:
    async def go():
        async with Client(build_server(_ledger(tmp_path))) as c:
            return await c.list_tools()

    tools = {t.name: t for t in asyncio.run(go()).tools}
    assert set(tools) == {"list_questions", "get_question", "leaderboard", "run_sql"}
    assert all(t.annotations and t.annotations.read_only_hint for t in tools.values())


def test_questions_question_and_leaderboard(tmp_path) -> None:
    server = build_server(_ledger(tmp_path))
    rows = call(server, "list_questions", {"status": "resolved"}).structured_content
    assert [r["outcome"] for r in rows["result"]] == ["YES"]
    q = question()
    one = call(server, "get_question", {"question_id": q.question_id}).structured_content
    assert one["observed_value"] == 91.2 and {f["forecaster"] for f in one["forecasts"]} == {
        "base_rate", "llm_context"}  # fmt: skip
    board = call(server, "leaderboard").structured_content
    by = {r["forecaster"]: r for r in board["rows"]}
    assert by["llm_context"]["brier"] == pytest.approx(0.04) and "rehearsal" in board["note"]
    bad = call(server, "get_question", {"question_id": "nope"})
    assert bad.is_error


def test_sql_is_read_only(tmp_path) -> None:
    b = Benchmark(_ledger(tmp_path))
    out = b.run_sql("SELECT forecaster_id, probability FROM forecasts ORDER BY 1, 2")
    assert out["columns"] == ["forecaster_id", "probability"] and len(out["rows"]) == 3
    for q in ("DROP TABLE forecasts", "SELECT 1; DROP TABLE forecasts",
              "INSERT INTO skips VALUES ('a', 'b', 'c')", "ATTACH 'x.db'"):  # fmt: skip
        with pytest.raises(SqlRefused):
            check_sql(q)
    secret = tmp_path / "outside.csv"
    secret.write_text("a\n1\n")
    with pytest.raises(Exception, match=r"(?i)external|disabled|permission"):
        b.run_sql(f"SELECT * FROM read_csv('{secret}')")
    with pytest.raises(Exception, match=r"(?i)lock|configuration"):
        b.con.execute("SET enable_external_access = true")
    assert call(
        build_server(_ledger(tmp_path / "b")), "run_sql", {"query": "DELETE FROM x"}
    ).is_error


def test_stdio_end_to_end(tmp_path) -> None:
    led = _ledger(tmp_path)
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "arena.cli", "--ledger-dir", str(led.root), "mcp"],
        env={**os.environ},
    )  # fmt: skip

    async def go():
        async with Client(params) as c:
            r = await c.call_tool("run_sql", {"query": "SELECT count(*) AS n FROM questions"})
            return r

    r = asyncio.run(go())
    assert not r.is_error and r.structured_content["rows"] == [[2]]
    assert json.loads(json.dumps(r.structured_content))  # plain JSON over the wire
