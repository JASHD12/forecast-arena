"""`agent_hybrid`: the agent with hybrid retrieval and guarded tool text (T274, experimental).

Same tools, limits, prompt and daily sample as `agent`. Two differences, both visible in the version
string: the "similar past questions" tool ranks with BM25 + dense vectors fused by reciprocal rank
fusion and a cross-encoder reranker (same leakage rule as the live retriever), and every tool result
(news headlines, Wikipedia text, retrieved questions) passes through the harness-level guards
before the model reads it; the flags are written to the trace.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from arena.agent.forecaster import AgentForecaster
from arena.llm import guards
from arena.llm.client import LLMClient
from arena.models import Forecast, Question, Skip

GUARD_VERSION = "guards-r1"
Rerank = Callable[[str, Sequence[str]], Sequence[float]]


def _guard(result: Any) -> tuple[Any, list[str]]:
    return guards.sanitize_tree(result)


class AgentHybrid(AgentForecaster):
    """`agent_hybrid`; a missing reranker or retriever is a `model_missing` skip with the reason."""

    forecaster_id = "agent_hybrid"

    def __init__(
        self,
        client: LLMClient | None,
        *,
        reranker: Rerank | None = None,
        reranker_name: str = "none",
        missing: str | None = None,
        **kw: Any,
    ) -> None:
        kw.setdefault("prompt_version", "v2")  # the prompt that describes the retrieval tool
        super().__init__(client, guard=_guard, **kw)
        self.reranker, self.reranker_name, self.missing = reranker, reranker_name, missing

    def version(self) -> str:
        """The agent version plus the retriever and the guard version."""
        return f"{super().version()}|hybrid-{self.reranker_name}|{GUARD_VERSION}"

    def _similar(self, q: Question, asof: datetime) -> Callable[[int, bool], dict[str, Any]] | None:
        r = self.retriever
        if r is None:
            return None

        def run(k: int, same_domain: bool) -> dict[str, Any]:
            return r.tool_result_hybrid(
                q.text,
                asof,
                k=k,
                exclude=q.question_id,
                domain=q.domain if same_domain else None,
                rerank=self.reranker,
                reranker_name=self.reranker_name,
            )

        return run

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        if self.missing is not None:
            return self._skip(q, "model_missing", self.missing, asof)
        return super().forecast(q, ctx, asof)
