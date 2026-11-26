"""T364 contract test: `arena-oracle` answers equal the MCP server's on the offline e2e ledger.

Both interfaces are built on `arena.mcp_server.Benchmark`; this test keeps them from drifting apart
(for example if one of them started to post-process results) and checks, on a ledger produced by the
full offline schedule, that the A2A answers contain every question and board row the MCP tools list.
"""

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("a2a")

from test_e2e import run_schedule

from arena.a2a import oracle
from arena.a2a.transport import InProcessHub, run_sync
from arena.mcp_server import Benchmark


def _floats(obj: Any) -> Any:
    if obj is None or isinstance(obj, bool | str):
        return obj
    if isinstance(obj, int | float):
        return float(obj)
    if isinstance(obj, list):
        return [_floats(x) for x in obj]
    return {k: _floats(v) for k, v in obj.items()}


def _a2a(led: Any, payload: dict[str, Any]) -> dict[str, Any]:
    o = oracle.Oracle.from_ledger(led)

    async def go() -> Any:
        async with InProcessHub({oracle.NAME: (oracle.oracle_spec(), o.handle)}) as hub:
            return await hub.client(oracle.NAME).ask(payload)

    r = run_sync(go())
    assert r.ok and r.data is not None, r.error
    return r.data


def test_oracle_equals_the_mcp_benchmark_on_the_e2e_ledger(tmp_path: Path) -> None:
    led = run_schedule(tmp_path / "ledger")
    b = Benchmark(led)
    listed = b.list_questions(None, "all", 200)
    assert listed, "the e2e ledger has questions"
    data = _a2a(led, {"skill": "list_questions", "args": {"limit": 200}})
    assert data["result"] == _floats(json.loads(json.dumps(listed, default=str)))
    first = listed[0]["question_id"]
    one = _a2a(led, {"skill": "get_question", "args": {"question_id": first}})
    assert one["result"] == _floats(json.loads(json.dumps(b.get_question(first), default=str)))
    board = _a2a(led, {"skill": "leaderboard", "args": {}})
    assert board["result"] == _floats(json.loads(json.dumps(b.leaderboard(None), default=str)))
    assert board["result"]["rows"], "the e2e ledger has scored forecasts"
