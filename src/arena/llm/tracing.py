"""LLM tracing (T123): one span per model call, written with the day's agent traces.

A span is OpenTelemetry-shaped but stored as plain JSON (no collector, no service): name,
start time, duration and attributes. Attributes: forecaster and question, provider and
model, prompt version, input and output tokens, the tools the model asked for, the stop
reason, whether the call was a repair request, and the error if the call failed. Spans
never contain prompt or answer text, so they add no copyrighted or personal data.

The morning job opens a scope per (forecaster, question) with `scope()`; every call made
through `TracingLLM` inside it is recorded in the run's `Tracer`. Calls outside a scope are
recorded with empty ids (they still count).
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any

from arena.clock import Clock
from arena.llm.client import LLMClient, LLMResponse, ToolSpec, Turn, UserText

_SCOPE: contextvars.ContextVar[tuple[str, str, str]] = contextvars.ContextVar(
    "arena_llm_scope", default=("", "", "")
)
#: The start of every repair prompt (all prompt versions share it).
REPAIR_PREFIX = "Your previous answer could not be parsed"


@dataclass(frozen=True)
class Span:
    """One model call."""

    name: str
    forecaster_id: str
    question_id: str
    prompt_version: str
    seq: int
    start: str
    duration_ms: float
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    tools_requested: list[str] = field(default_factory=list)
    stop_reason: str = ""
    repair: bool = False
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """JSON-ready form."""
        return asdict(self)


@dataclass
class Tracer:
    """Collects the spans of one run."""

    spans: list[Span] = field(default_factory=list)

    def for_pair(self, forecaster_id: str, question_id: str) -> list[dict[str, Any]]:
        """Spans of one forecaster on one question, in call order."""
        return [s.as_dict() for s in self.spans
                if s.forecaster_id == forecaster_id and s.question_id == question_id]  # fmt: skip

    def pairs(self) -> list[tuple[str, str]]:
        """(forecaster, question) pairs that made at least one call, sorted."""
        return sorted({(s.forecaster_id, s.question_id) for s in self.spans})


@contextmanager
def scope(forecaster_id: str, question_id: str, prompt_version: str = "") -> Iterator[None]:
    """Attribute the calls made inside to this forecaster and question."""
    token = _SCOPE.set((forecaster_id, question_id, prompt_version))
    try:
        yield
    finally:
        _SCOPE.reset(token)


def _is_repair(turns: Sequence[Turn]) -> bool:
    return (
        bool(turns) and isinstance(turns[-1], UserText) and turns[-1].text.startswith(REPAIR_PREFIX)
    )


class TracingLLM:
    """An `LLMClient` that records a span for every call of the wrapped client."""

    def __init__(
        self,
        inner: LLMClient,
        tracer: Tracer,
        clock: Clock,
    ) -> None:
        self.inner = inner
        self.provider = inner.provider
        self.model = inner.model
        self.tracer = tracer
        self.clock = clock

    def sampling(self) -> dict[str, Any]:
        """The wrapped client's sampling settings."""
        return self.inner.sampling()

    def complete(
        self, system: str, turns: Sequence[Turn], *, max_tokens: int, tools: Sequence[ToolSpec] = ()
    ) -> LLMResponse:
        """See `LLMClient.complete`; records a span, also when the call raises."""
        fid, qid, pv = _SCOPE.get()
        seq = sum(1 for s in self.tracer.spans if s.forecaster_id == fid and s.question_id == qid)
        start = self.clock.now()
        base: dict[str, Any] = {"name": "llm.complete", "forecaster_id": fid, "question_id": qid,
                "prompt_version": pv, "seq": seq, "start": start.isoformat(),
                "provider": self.inner.provider, "model": self.inner.model,
                "repair": _is_repair(turns)}  # fmt: skip
        try:
            resp = self.inner.complete(system, turns, max_tokens=max_tokens, tools=tools)
        except Exception as exc:
            ms = round((self.clock.now() - start).total_seconds() * 1000, 1)
            self.tracer.spans.append(Span(**base, duration_ms=ms,
                                          error=f"{type(exc).__name__}: {exc}"[:200]))  # fmt: skip
            raise
        ms = round((self.clock.now() - start).total_seconds() * 1000, 1)
        self.tracer.spans.append(
            Span(
                **base,
                duration_ms=ms,
                input_tokens=resp.usage.input_tokens,
                output_tokens=resp.usage.output_tokens,
                tools_requested=[c.name for c in resp.tool_calls],
                stop_reason=resp.stop_reason,
            )
        )
        return resp
