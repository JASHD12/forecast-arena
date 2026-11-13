"""LLM tracing (T123): spans per call, scopes, and the observability numbers."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from factories import B

from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.llm.client import FakeLLM, LLMError, ToolCall, UserText, tool_reply
from arena.llm.tracing import REPAIR_PREFIX, Tracer, TracingLLM, scope
from arena.site.llm_obs import load_spans, price_for, totals, traces_by_question, usage_rows

T0 = datetime(2026, 11, 12, 5, 30, tzinfo=UTC)


class StepClock(FixedClock):
    """Moves forward 2 s every time it is read."""

    def now(self) -> datetime:
        t = super().now()
        self.set(t + timedelta(seconds=2))
        return t


def test_spans_record_scope_tokens_tools_latency_and_repairs() -> None:
    tr = Tracer()
    fake = FakeLLM([tool_reply(ToolCall("c", "get_series", {"key": "list"})), "x", "y"])
    llm = TracingLLM(fake, tr, StepClock(T0))
    assert llm.provider == fake.provider and llm.model == fake.model
    with scope("agent", "q1", "v2"):
        llm.complete("s", [UserText("hi")], max_tokens=10)
        llm.complete("s", [UserText(REPAIR_PREFIX + ": bad")], max_tokens=10)
    llm.complete("s", [UserText("outside")], max_tokens=10)
    a, b, c = tr.spans
    assert (a.forecaster_id, a.question_id, a.prompt_version, a.seq) == ("agent", "q1", "v2", 0)
    assert a.tools_requested == ["get_series"] and not a.repair and a.duration_ms == 2000.0
    assert b.seq == 1 and b.repair and b.input_tokens == fake.tokens_per_call[0]
    assert c.forecaster_id == "" and c.seq == 0  # outside any scope, still recorded
    assert tr.pairs() == [("", ""), ("agent", "q1")] and len(tr.for_pair("agent", "q1")) == 2


def test_a_failing_call_is_traced_and_reraised() -> None:
    def boom(system, turns, tools):
        raise LLMError("overloaded")

    tr = Tracer()
    with scope("llm_plain", "q"), pytest.raises(LLMError):
        TracingLLM(FakeLLM(boom), tr, FixedClock(T0)).complete("s", [], max_tokens=5)
    (s,) = tr.spans
    assert s.error == "LLMError: overloaded" and s.output_tokens == 0


def test_observability_rows_prices_and_traces(tmp_path) -> None:
    led = Ledger(tmp_path)
    span = {
        "forecaster_id": "agent",
        "question_id": "q1",
        "provider": "anthropic",
        "model": "claude-haiku-5-5",
        "input_tokens": 1_000_000,
        "output_tokens": 200_000,
        "duration_ms": 1500.0,
        "repair": False,
        "error": None,
        "seq": 0,
    }
    local = {
        **span,
        "forecaster_id": "llm_local",
        "provider": "llama_cpp",
        "model": "qwen",
        "duration_ms": 20000.0,
    }
    odd = {**span, "forecaster_id": "llm_plain", "model": "some-other-model", "error": "x"}
    lines = [
        {
            "forecaster_id": "agent",
            "question_id": "q1",
            "outcome": "forecast",
            "tool_calls": [],
            "spans": [span],
        },
        {
            "forecaster_id": "llm_local",
            "question_id": "q1",
            "outcome": "forecast",
            "spans": [local],
        },
        {"forecaster_id": "llm_plain", "question_id": "q2", "outcome": "error", "spans": [odd]},
    ]
    body = "".join(json.dumps(x) + "\n" for x in lines).encode()
    led.write_raw(layout.agent_traces_path(B), body)
    rows = {r.forecaster_id: r for r in usage_rows(load_spans(led))}
    assert rows["agent"].cost_usd == pytest.approx(0.10 + 0.10)  # 1M in + 0.2M out
    assert rows["agent"].day == B and rows["agent"].p50_ms == 1500.0
    assert rows["llm_local"].cost_usd == 0.0
    assert rows["llm_plain"].cost_usd is None and rows["llm_plain"].errors == 1
    assert rows["llm_plain"].p50_ms is None  # failed calls have no latency figure
    t = totals(list(rows.values()))
    assert t["calls"] == 3 and t["unpriced"] == 1 and t["cost_usd"] == pytest.approx(0.2)
    assert price_for("anthropic", "claude-haiku-5-5-x") == (0.10, 0.50)
    by_q = traces_by_question(led)
    assert [x["forecaster_id"] for x in by_q["q1"]] == ["agent", "llm_local"]
