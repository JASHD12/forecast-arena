"""`agent_graph` (T121): the LangGraph agent, scripted with FakeLLM."""

import json
from datetime import UTC, datetime

import pytest

pytest.importorskip("langgraph")

from factories import question

from arena.agent.graph import GraphAgentForecaster
from arena.agent.retrieval import HashEmbedder, PastQuestions
from arena.forecasters.base import StaticHistory
from arena.forecasters.baselines import BaseRate
from arena.llm.budget import BudgetGuard, Caps, GuardedLLM
from arena.llm.client import (
    AssistantTurn,
    FakeLLM,
    LLMError,
    ToolCall,
    ToolResults,
    Usage,
    UserText,
    tool_reply,
)
from arena.models import Forecast, Skip

ASOF = datetime(2026, 11, 12, 6, tzinfo=UTC)
DRAFT = json.dumps({"probability": 0.6, "rationale": "Draft.", "key_factors": ["a"]})
FINAL = json.dumps({"probability": 0.45, "rationale": "Checked.", "key_factors": ["b"]})
PLAN = "Reference class: recent daily means. Check the trend."


def graph(llm, **kw):
    return GraphAgentForecaster(llm, peers={"base_rate": BaseRate(StaticHistory({}))}, **kw)


def kinds(turns):
    return [type(t).__name__ for t in turns]


def test_full_path_plan_retrieve_research_tools_critique() -> None:
    q = question()
    fake = FakeLLM([PLAN, tool_reply(ToolCall("c1", "get_series", {"key": "list"})), DRAFT, FINAL])
    out = graph(fake).forecast(q, {"daily": [1, 2]}, ASOF)
    assert isinstance(out, Forecast) and out.forecaster_id == "agent_graph"
    assert out.probability == 0.45  # the critique's answer counts, not the draft
    assert out.meta["graph_path"] == ["plan", "retrieve", "research", "tools", "research",
                                      "critique"]  # fmt: skip
    assert out.meta["usage"]["requests"] == 4
    assert out.meta["tool_calls"] == 2  # the automatic base rate + one model call
    assert "graph-prompt-v1" in out.forecaster_version and "langgraph-" in out.forecaster_version
    # Every request offers the tools; the evidence turn carries the base rate.
    assert all(c[2] for c in fake.calls)
    evidence = fake.calls[1][1][2]
    assert isinstance(evidence, UserText) and "get_base_rate" in evidence.text
    # The research reply's tool call was answered before the model was asked again.
    assert kinds(fake.calls[2][1])[-2:] == ["AssistantTurn", "ToolResults"]


def test_trace_and_retrieval_with_a_retriever(tmp_path) -> None:
    from arena.ledger import Ledger

    idx = PastQuestions.from_ledger(Ledger(tmp_path), HashEmbedder())  # empty: no matches
    f = graph(FakeLLM([PLAN, DRAFT, FINAL]), retriever=idx)
    out = f.forecast(question(), {}, ASOF)
    assert isinstance(out, Forecast) and "rag-hash-bow-256" in out.forecaster_version
    (line,) = f.trace_lines()
    assert [t["tool"] for t in line["tool_calls"]] == ["get_base_rate", "similar_past_questions"]
    assert line["graph_path"] == ["plan", "retrieve", "research", "critique"]


def test_tool_limit_forces_an_answer() -> None:
    burst = tool_reply(*[ToolCall(f"c{i}", "get_series", {"key": "list"}) for i in range(6)])
    fake = FakeLLM([PLAN, burst, DRAFT, FINAL])
    out = graph(fake, max_tool_calls=2).forecast(question(), {}, ASOF)
    assert isinstance(out, Forecast)
    assert out.meta["graph_path"] == ["plan", "retrieve", "research", "tools", "research",
                                      "critique"]  # fmt: skip
    asked = fake.calls[2][1][-1]
    assert isinstance(asked, UserText) and "limit" in asked.text  # agent_final prompt


def test_critique_tool_call_is_closed_before_the_repair() -> None:
    sneaky = tool_reply(ToolCall("c9", "get_series", {"key": "list"}))
    fake = FakeLLM([PLAN, DRAFT, sneaky, FINAL])
    out = graph(fake).forecast(question(), {}, ASOF)
    assert isinstance(out, Forecast) and out.probability == 0.45
    assert out.meta["graph_path"][-1] == "repair"
    last = fake.calls[-1][1]
    assert kinds(last)[-3:] == ["AssistantTurn", "ToolResults", "UserText"]
    assert isinstance(last[-3], AssistantTurn) and isinstance(last[-2], ToolResults)
    assert all(r[2] for r in last[-2].results)  # refused, not run


def test_two_bad_answers_are_a_parse_failure_skip() -> None:
    f = graph(FakeLLM([PLAN, DRAFT, "not json", "still not json"]))
    out = f.forecast(question(), {}, ASOF)
    assert isinstance(out, Skip) and out.reason_code == "parse_failure"
    (line,) = f.trace_lines()
    assert line["outcome"] == "parse_failure" and line["usage"]["requests"] == 4


def test_caps_hold_inside_the_graph() -> None:
    caps = Caps(max_requests_per_day=2, max_tokens_per_day=10**6, max_output_tokens=400,
                max_tool_calls=4)  # fmt: skip
    guard = BudgetGuard(caps, Usage())
    fake = FakeLLM([PLAN, DRAFT, FINAL])
    out = graph(GuardedLLM(fake, guard)).forecast(question(), {}, ASOF)
    assert isinstance(out, Skip) and out.reason_code == "budget_exhausted"
    assert len(fake.calls) == 2 and guard.used.requests == 2  # the third call never left


def test_errors_sampling_and_missing_model() -> None:
    q = question()

    def boom(system, turns, tools):
        raise LLMError("provider down")

    out = graph(FakeLLM(boom)).forecast(q, {}, ASOF)
    assert isinstance(out, Skip) and out.reason_code == "error"
    f = graph(FakeLLM([PLAN, DRAFT, FINAL]))
    f.prepare([q, question(template="max_gt")])
    assert len(f.sample or ()) == 1  # one question per domain per day
    skipped = [
        x for x in (question(), question(template="max_gt")) if x.question_id not in f.sample
    ]
    assert f.forecast(skipped[0], {}, ASOF).reason_code == "not_sampled"  # type: ignore[union-attr]
    assert graph(None).forecast(q, {}, ASOF).reason_code == "model_missing"  # type: ignore[union-attr]


def test_wiring_adds_agent_graph_only_when_switched_on(tmp_path) -> None:
    from factories import B

    from arena.config import Settings
    from arena.ledger import Ledger
    from arena.ops.wiring import build_forecasters

    led = Ledger(tmp_path)
    on, _ = build_forecasters(led, [], Settings.from_env({"ARENA_AGENT_GRAPH": "1"}), B,
                              llm=FakeLLM([FINAL]))  # fmt: skip
    off, _ = build_forecasters(led, [], Settings.from_env({}), B, llm=FakeLLM([FINAL]))
    assert [f.forecaster_id for f in on][-1] == "agent_graph"
    assert "agent_graph" not in [f.forecaster_id for f in off]
