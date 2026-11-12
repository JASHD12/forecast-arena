"""LLM client protocol, a scripted `FakeLLM`, and usage accounting (SPEC 9.1).

Conversations use a small provider-neutral shape so the agent loop is written once:
`UserText`, `AssistantTurn` (a previous response, re-sent as the provider returned it) and
`ToolResults`. Adapters translate to each provider's wire format. Usage is always taken
from the provider's own usage fields.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol


class LLMError(Exception):
    """The provider call failed (after the adapter's own retries)."""


class LLMRefusal(LLMError):
    """The model declined to answer (e.g. Anthropic `stop_reason: "refusal"`)."""


@dataclass(frozen=True)
class ToolSpec:
    """A read-only tool offered to the model."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """A tool call requested by the model."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class Usage:
    """Tokens and requests as reported by the provider."""

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Input plus output tokens (what the daily cap counts)."""
        return self.input_tokens + self.output_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.requests + other.requests,
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
        )

    def as_dict(self) -> dict[str, int]:
        """For run manifests."""
        return {
            "requests": self.requests,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


@dataclass(frozen=True)
class LLMResponse:
    """One model turn."""

    text: str
    tool_calls: tuple[ToolCall, ...]
    stop_reason: str
    model: str
    usage: Usage
    raw: Any = None  # provider-native assistant content, re-sent in tool loops


@dataclass(frozen=True)
class UserText:
    """A user message."""

    text: str


@dataclass(frozen=True)
class AssistantTurn:
    """An earlier response of the model."""

    response: LLMResponse


@dataclass(frozen=True)
class ToolResults:
    """Results for the tool calls of the previous assistant turn."""

    results: tuple[tuple[str, str, bool], ...]  # (tool_call_id, content, is_error)


Turn = UserText | AssistantTurn | ToolResults


class LLMClient(Protocol):
    """What forecasters need from a provider."""

    provider: str
    model: str

    def sampling(self) -> dict[str, Any]:
        """Sampling settings actually sent (recorded on every forecast)."""
        ...

    def complete(
        self, system: str, turns: Sequence[Turn], *, max_tokens: int, tools: Sequence[ToolSpec] = ()
    ) -> LLMResponse:
        """One request. Raises LLMError/LLMRefusal on failure."""
        ...


Script = Callable[[str, Sequence[Turn], Sequence[ToolSpec]], LLMResponse | str | Exception]


@dataclass
class FakeLLM:
    """Scripted client for tests: a list of replies (strings, responses or exceptions)
    consumed in order, or a function of (system, turns, tools)."""

    replies: list[LLMResponse | str | Exception] | Script = field(default_factory=list)
    model: str = "fake-model-1"
    provider: str = "fake"
    tokens_per_call: tuple[int, int] = (100, 20)
    calls: list[tuple[str, list[Turn], list[ToolSpec]]] = field(default_factory=list)

    def sampling(self) -> dict[str, Any]:
        """See `LLMClient.sampling`."""
        return {"temperature": 0.0}

    def complete(
        self, system: str, turns: Sequence[Turn], *, max_tokens: int, tools: Sequence[ToolSpec] = ()
    ) -> LLMResponse:
        """See `LLMClient.complete`."""
        self.calls.append((system, list(turns), list(tools)))
        if callable(self.replies):
            reply = self.replies(system, turns, tools)
        else:
            if not self.replies:
                raise LLMError("FakeLLM has no scripted reply left")
            reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, LLMResponse):
            return reply
        i, o = self.tokens_per_call
        return LLMResponse(reply, (), "end_turn", self.model, Usage(1, i, o))


def tool_reply(*calls: ToolCall, model: str = "fake-model-1", text: str = "") -> LLMResponse:
    """A scripted response that requests tool calls (for FakeLLM scripts)."""
    return LLMResponse(text, tuple(calls), "tool_use", model, Usage(1, 100, 20))
