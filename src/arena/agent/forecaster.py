"""The `agent` forecaster (SPEC 8, 9.3): an LLM with read-only tools in a bounded loop.

The harness, not the model, enforces every rule: at most `max_tool_calls` tool calls and
`time_limit` seconds per question, the daily budget (through the guarded client), the
fixed output contract (strict parsing, one repair retry) and as-of data only. Tool output
is passed back verbatim as data; nothing in it can change the harness's behaviour.
Compact traces (tool names, arguments, sizes, source URLs) are kept per question and
written by the morning job to `agent_traces/`.
"""

from __future__ import annotations

import time as _time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any

from arena.agent.tools import SIMILAR_SPEC, TOOL_SPECS, NewsBackend, ToolBox
from arena.forecasters.base import Forecaster
from arena.forecasters.llm import daily_sample, render_context
from arena.llm import prompts
from arena.llm.budget import BudgetExhausted
from arena.llm.client import (
    AssistantTurn,
    LLMClient,
    LLMError,
    LLMResponse,
    ToolResults,
    Turn,
    Usage,
    UserText,
)
from arena.llm.parse import ParseError, parse_answer
from arena.models import Forecast, Question, Skip

if TYPE_CHECKING:
    from arena.agent.retrieval import PastQuestions


class AgentForecaster:
    """`agent`: as llm_context plus tools."""

    forecaster_id = "agent"
    max_output_tokens = 400
    prompt_files: tuple[str, ...] = ("agent_system", "agent_user", "agent_final", "repair")

    def __init__(
        self,
        client: LLMClient | None,
        *,
        per_domain: int = 3,
        max_tool_calls: int = 4,
        time_limit: float = 90.0,
        peers: Mapping[str, Forecaster] | None = None,
        news: NewsBackend | None = None,
        wiki: Callable[[str, str], dict[str, str]] | None = None,
        monotonic: Callable[[], float] = _time.monotonic,
        prompt_version: str = prompts.PROMPT_VERSION,
        retriever: PastQuestions | None = None,
    ) -> None:
        self.client = client
        self.per_domain = per_domain
        self.max_tool_calls = max_tool_calls
        self.time_limit = time_limit
        self.peers = dict(peers or {})
        self.news = news
        self.wiki = wiki
        self.monotonic = monotonic
        self.prompt_version = prompt_version
        #: The RAG tool is offered only with a retriever (prompt v2 describes it).
        self.retriever = retriever
        self.tools = (*TOOL_SPECS, SIMILAR_SPEC) if retriever is not None else TOOL_SPECS
        self.sample: set[str] | None = None
        self.traces: dict[str, dict[str, Any]] = {}

    def prepare(self, questions: Sequence[Question]) -> None:
        """Same seeded daily sample as the other LLM forecasters."""
        self.sample = daily_sample(questions, self.per_domain)

    def version(self) -> str:
        """Model id, prompt version and tool limits."""
        model = self.client.model if self.client is not None else "none"
        fp = prompts.fingerprint(self.prompt_files, self.prompt_version)
        rag = f"|rag-{self.retriever.embedder.name}" if self.retriever is not None else ""
        return (
            f"{model}|prompt-{self.prompt_version}-{fp}|tools-{self.max_tool_calls}{rag}"
            f"|out-{self.max_output_tokens}"
        )

    def _similar(self, q: Question, asof: datetime) -> Callable[[int, bool], dict[str, Any]] | None:
        """The RAG tool bound to this question and forecast time (I3: asof filter)."""
        r = self.retriever
        if r is None:
            return None

        def run(k: int, same_domain: bool) -> dict[str, Any]:
            return r.tool_result(
                q.text, asof, k=k, exclude=q.question_id, domain=q.domain if same_domain else None
            )

        return run

    def _skip(self, q: Question, reason: str, detail: str, asof: datetime) -> Skip:
        return Skip(
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=self.version(),
            reason_code=reason,  # type: ignore[arg-type]
            detail=detail[:300],
            created_at=asof,
        )

    def _peer_probabilities(
        self, q: Question, ctx: dict[str, Any], asof: datetime
    ) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for fid, f in self.peers.items():
            try:
                r = f.forecast(q, ctx, asof)
            except Exception:  # a failing peer only means the tool has no value
                continue
            if isinstance(r, Forecast):
                out[fid] = {q.question_id: r.probability}
        return out

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        if self.client is None:
            return self._skip(q, "model_missing", "no LLM configured", asof)
        if self.sample is not None and q.question_id not in self.sample:
            return self._skip(q, "not_sampled", "not in today's LLM sample", asof)
        box = ToolBox(
            ctx,
            asof,
            probabilities=self._peer_probabilities(q, ctx, asof),
            news=self.news,
            wiki=self.wiki,
            similar=self._similar(q, asof),
            max_calls=self.max_tool_calls,
            time_limit=self.time_limit,
            monotonic=self.monotonic,
        )
        system = prompts.load("agent_system", self.prompt_version).replace(
            "{max_calls}", str(self.max_tool_calls)
        )
        turns: list[Turn] = [UserText(self._user_prompt(q, ctx, asof))]
        usage = Usage()
        try:
            answer_text, resp, usage = self._loop(system, turns, box, usage)
            try:
                answer = parse_answer(answer_text)
            except ParseError as first:
                repair = prompts.load("repair", self.prompt_version).replace("{error}", str(first))
                # `_loop` already appended the model's reply to `turns`; adding it again
                # would send two assistant messages in a row, which the API merges and
                # then rejects for modified thinking blocks (seen live on 2026-11-13).
                turns = [*turns, UserText(repair)]
                resp = self.client.complete(
                    system, turns, max_tokens=self.max_output_tokens, tools=self.tools
                )
                usage = usage + resp.usage
                answer = parse_answer(resp.text)
        except BudgetExhausted as exc:
            self._trace(q, box, usage, "budget_exhausted")
            return self._skip(q, "budget_exhausted", str(exc), asof)
        except LLMError as exc:
            self._trace(q, box, usage, "error")
            return self._skip(q, "error", f"{type(exc).__name__}: {exc}", asof)
        except ParseError as exc:
            self._trace(q, box, usage, "parse_failure")
            return self._skip(q, "parse_failure", f"two unparseable answers: {exc}", asof)
        self._trace(q, box, usage, "forecast")
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
                "usage": usage.as_dict(),
                "tool_calls": len(box.trace),
            },
        )

    def _loop(
        self, system: str, turns: list[Turn], box: ToolBox, usage: Usage
    ) -> tuple[str, LLMResponse, Usage]:
        """Call the model; run requested tools within the limits; return the final text."""
        assert self.client is not None
        while True:
            resp = self.client.complete(
                system, turns, max_tokens=self.max_output_tokens, tools=self.tools
            )
            usage = usage + resp.usage
            turns.append(AssistantTurn(resp))
            if not resp.tool_calls:
                return resp.text, resp, usage
            results = tuple((c.id, *box.run(c)) for c in resp.tool_calls)
            turns.append(ToolResults(results))
            if box.calls_left <= 0 or box.time_left() <= 0:
                turns.append(UserText(prompts.load("agent_final", self.prompt_version)))
                resp = self.client.complete(
                    system, turns, max_tokens=self.max_output_tokens, tools=self.tools
                )
                usage = usage + resp.usage
                turns.append(AssistantTurn(resp))
                return resp.text, resp, usage

    def _user_prompt(self, q: Question, ctx: dict[str, Any], asof: datetime) -> str:
        return (
            prompts.load("agent_user", self.prompt_version)
            .replace("{today}", asof.date().isoformat())
            .replace("{lock_time}", q.lock_time.strftime("%Y-%m-%d %H:%M UTC"))
            .replace("{asof}", asof.strftime("%Y-%m-%d %H:%M UTC"))
            .replace("{question_id}", q.question_id)
            .replace("{question}", q.text)
            .replace("{rule}", q.resolution_rule)
            .replace("{context}", render_context(ctx))
        )

    def _trace(self, q: Question, box: ToolBox, usage: Usage, outcome: str) -> None:
        self.traces[q.question_id] = {
            "question_id": q.question_id,
            "outcome": outcome,
            "tool_calls": box.compact_trace(),
            "usage": usage.as_dict(),
        }

    def trace_lines(self) -> list[dict[str, Any]]:
        """Traces of this run, by question id (for `agent_traces/`)."""
        return [self.traces[k] for k in sorted(self.traces)]
