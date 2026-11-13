"""`agent_graph`: the agent as an explicit LangGraph state machine (T121, SPEC 8.8).

    plan -> retrieve -> research <-> tools -> critique -> answer

- plan: the model writes a short plan (no tools used).
- retrieve: no model call; the base rate and, with a retriever, the similar past
  questions (T120) are fetched through the same `ToolBox` and handed to the model.
- research <-> tools: the model may call the read-only tools within the limits; when a
  limit is reached it is asked to answer.
- critique: the model checks its draft against the rule and the references.
- answer: parse the final JSON; one repair request if it does not parse.

Every model call goes through the project's own `LLMClient`, so `GuardedLLM` and its
`BudgetGuard` enforce the daily caps exactly as for the other LLM forecasters, and tests
use `FakeLLM`. LangGraph only orchestrates the steps. The output contract, sampling,
skips and trace format are the hand-written agent's (`agent/forecaster.py`); the research
question is whether the extra structure changes forecast quality, same model, same tools.
"""

from __future__ import annotations

import json
from datetime import datetime
from importlib.metadata import version as _pkg_version
from typing import Any, Literal, TypedDict

from arena.agent.forecaster import AgentForecaster
from arena.agent.tools import ToolBox
from arena.llm import prompts
from arena.llm.budget import BudgetExhausted
from arena.llm.client import (
    AssistantTurn,
    LLMError,
    LLMResponse,
    ToolCall,
    ToolResults,
    Turn,
    Usage,
    UserText,
)
from arena.llm.parse import ParseError, parse_answer
from arena.models import Forecast, Question, Skip

GRAPH_PROMPT_VERSION = "v1"
#: Retrieval calls made by the `retrieve` node on top of the model's own tool budget.
AUTO_CALLS = 2


class State(TypedDict, total=False):
    """What flows between the nodes."""

    turns: list[Turn]
    usage: Usage
    resp: LLMResponse | None
    final: bool
    path: list[str]


class GraphAgentForecaster(AgentForecaster):
    """The agent with the same tools and contract, run as a LangGraph graph."""

    forecaster_id = "agent_graph"
    prompt_files: tuple[str, ...] = (
        "graph_system", "graph_plan", "graph_evidence", "graph_critique",
        "agent_user", "agent_final", "repair",
    )  # fmt: skip

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("per_domain", 1)
        kwargs.setdefault("prompt_version", GRAPH_PROMPT_VERSION)
        super().__init__(*args, **kwargs)
        self._spent = Usage()  # usage of the current question, also when a call raises

    def version(self) -> str:
        """Model id, prompt fingerprint, tool limit, retrieval and LangGraph version."""
        model = self.client.model if self.client is not None else "none"
        fp = prompts.fingerprint(self.prompt_files, self.prompt_version)
        rag = f"|rag-{self.retriever.embedder.name}" if self.retriever is not None else ""
        lg = _pkg_version("langgraph")
        return (f"{model}|graph-prompt-{self.prompt_version}-{fp}|tools-{self.max_tool_calls}"
                f"{rag}|out-{self.max_output_tokens}|langgraph-{lg}")  # fmt: skip

    def _call(self, system: str, s: State) -> State:
        assert self.client is not None
        resp = self.client.complete(
            system, s["turns"], max_tokens=self.max_output_tokens, tools=self.tools
        )
        self._spent = self._spent + resp.usage
        return {
            "turns": [*s["turns"], AssistantTurn(resp)],
            "usage": s["usage"] + resp.usage,
            "resp": resp,
        }

    def _graph(self, q: Question, ctx: dict[str, Any], asof: datetime, box: ToolBox) -> Any:
        from langgraph.graph import END, START, StateGraph

        v = self.prompt_version
        system = prompts.load("graph_system", v).replace("{max_calls}", str(self.max_tool_calls))

        def step(name: str, s: State) -> list[str]:
            return [*s.get("path", []), name]

        def plan(s: State) -> State:
            turns: list[Turn] = [
                UserText(self._user_prompt(q, ctx, asof) + "\n\n" + prompts.load("graph_plan", v))
            ]
            out = self._call(system, {**s, "turns": turns})
            return {**out, "path": step("plan", s)}

        def retrieve(s: State) -> State:
            calls = [ToolCall("auto-base-rate", "get_base_rate", {"question_id": q.question_id})]
            if self.retriever is not None:
                calls.append(ToolCall("auto-similar", "similar_past_questions", {"k": 5}))
            evidence = {c.name: json.loads(box.run(c)[0]) for c in calls}
            text = prompts.load("graph_evidence", v).replace(
                "{evidence}", json.dumps(evidence, ensure_ascii=False, default=str)
            )
            return {"turns": [*s["turns"], UserText(text)], "path": step("retrieve", s)}

        def research(s: State) -> State:
            turns = s["turns"]
            if s.get("final"):
                turns = [*turns, UserText(prompts.load("agent_final", v))]
            out = self._call(system, {**s, "turns": turns})
            return {**out, "path": step("research", s)}

        def tools(s: State) -> State:
            resp = s["resp"]
            assert resp is not None
            results = tuple((c.id, *box.run(c)) for c in resp.tool_calls)
            done = box.calls_left <= 0 or box.time_left() <= 0
            return {"turns": [*s["turns"], ToolResults(results)], "final": done,
                    "path": step("tools", s)}  # fmt: skip

        def after_research(s: State) -> Literal["tools", "critique"]:
            resp = s["resp"]
            if resp is not None and resp.tool_calls and not s.get("final"):
                return "tools"
            return "critique"

        def critique(s: State) -> State:
            turns = self._close_tool_calls(s)
            out = self._call(
                system, {**s, "turns": [*turns, UserText(prompts.load("graph_critique", v))]}
            )
            return {**out, "path": step("critique", s)}

        g: Any = StateGraph(State)  # node callables are plain closures; overloads do not fit
        g.add_node("plan", plan)
        g.add_node("retrieve", retrieve)
        g.add_node("research", research)
        g.add_node("tools", tools)
        g.add_node("critique", critique)
        g.add_edge(START, "plan")
        g.add_edge("plan", "retrieve")
        g.add_edge("retrieve", "research")
        g.add_conditional_edges("research", after_research, ["tools", "critique"])
        g.add_edge("tools", "research")
        g.add_edge("critique", END)
        return g.compile()

    def _close_tool_calls(self, s: State) -> list[Turn]:
        """If the last reply asked for tools, answer them with a refusal first (the API
        needs a result for every tool call before the next user text)."""
        resp = s.get("resp")
        turns = s["turns"]
        if resp is not None and resp.tool_calls:
            msg = json.dumps({"error": "no more tool calls in this step"})
            turns = [*turns, ToolResults(tuple((c.id, msg, True) for c in resp.tool_calls))]
        return turns

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        if self.client is None:
            return self._skip(q, "model_missing", "no LLM configured", asof)
        if self.sample is not None and q.question_id not in self.sample:
            return self._skip(q, "not_sampled", "not in today's LLM sample", asof)
        box = ToolBox(
            ctx, asof, probabilities=self._peer_probabilities(q, ctx, asof), news=self.news,
            wiki=self.wiki, similar=self._similar(q, asof),
            max_calls=self.max_tool_calls + AUTO_CALLS, time_limit=self.time_limit,
            monotonic=self.monotonic,
        )  # fmt: skip
        self._spent = Usage()
        state: State = {"turns": [], "usage": Usage(), "resp": None, "final": False, "path": []}
        try:
            limit = 2 * (self.max_tool_calls + AUTO_CALLS) + 10
            state = self._graph(q, ctx, asof, box).invoke(state, {"recursion_limit": limit})
            resp = state["resp"]
            assert resp is not None
            try:
                answer = parse_answer(resp.text)
            except ParseError as first:
                repair = prompts.load("repair", self.prompt_version).replace("{error}", str(first))
                turns = [*self._close_tool_calls(state), UserText(repair)]
                system = prompts.load("graph_system", self.prompt_version)
                system = system.replace("{max_calls}", str(self.max_tool_calls))
                out = self._call(system, {**state, "turns": turns})
                state = {**state, **out, "path": [*state["path"], "repair"]}
                resp = out["resp"]
                assert resp is not None
                answer = parse_answer(resp.text)
        except BudgetExhausted as exc:
            return self._done_skip(q, box, state, "budget_exhausted", str(exc), asof)
        except LLMError as exc:
            return self._done_skip(q, box, state, "error", f"{type(exc).__name__}: {exc}", asof)
        except ParseError as exc:
            return self._done_skip(q, box, state, "parse_failure",
                                   f"two unparseable answers: {exc}", asof)  # fmt: skip
        self._graph_trace(q, box, state, "forecast")
        return Forecast(
            forecast_id=f"{q.question_id}::{self.forecaster_id}",
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=self.version(),
            probability=answer.probability,
            created_at=asof,
            rationale=answer.rationale,
            meta={
                "model": resp.model,
                "provider": self.client.provider,
                "prompt_version": self.prompt_version,
                "sampling": self.client.sampling(),
                "key_factors": list(answer.key_factors),
                "usage": state["usage"].as_dict(),
                "tool_calls": len(box.trace),
                "graph_path": state["path"],
            },
        )

    def _graph_trace(self, q: Question, box: ToolBox, state: State, outcome: str) -> None:
        self._trace(q, box, self._spent, outcome)
        self.traces[q.question_id]["graph_path"] = list(state.get("path", []))

    def _done_skip(
        self, q: Question, box: ToolBox, state: State, reason: str, detail: str, asof: datetime
    ) -> Skip:
        self._graph_trace(q, box, state, reason)
        return self._skip(q, reason, detail, asof)
