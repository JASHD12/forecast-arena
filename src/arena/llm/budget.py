"""Budget guard (SPEC 9.4): hard caps on LLM usage, counted across all runs of a UTC day.

Usage already spent today is summed from the day's run manifests on the ledger (their
`llm_usage`, taken from the provider's own usage fields) plus this run's recorder. Before
each call the guard checks, conservatively, that one more request fits and that the
tokens it could use (an input estimate plus the full output cap) fit under the daily
token cap. When a cap would be crossed, `BudgetExhausted` is raised and forecasters record
a `budget_exhausted` skip.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from arena.config import Settings
from arena.ledger import Ledger
from arena.ledger.manifest import RunRecorder, manifests_for_day
from arena.llm.client import (
    AssistantTurn,
    LLMClient,
    LLMResponse,
    ToolResults,
    ToolSpec,
    Turn,
    Usage,
    UserText,
)

CHARS_PER_TOKEN = 3  # conservative: real tokenisers average more characters per token


class BudgetExhausted(Exception):
    """A daily LLM cap would be exceeded."""


@dataclass(frozen=True)
class Caps:
    """The SPEC 9.4 caps."""

    max_requests_per_day: int
    max_tokens_per_day: int
    max_output_tokens: int
    max_tool_calls: int

    @classmethod
    def from_settings(cls, s: Settings) -> Caps:
        """Caps from ARENA_* settings."""
        return cls(
            s.llm_max_requests_per_day,
            s.llm_max_tokens_per_day,
            s.llm_max_output_tokens,
            s.agent_max_tool_calls,
        )


def usage_from_manifests(ledger: Ledger, day: date) -> Usage:
    """LLM usage recorded by every run started on UTC `day` (dry runs never reach the
    real ledger, so they are not in here)."""
    total = Usage()
    for m in manifests_for_day(ledger, day):
        u = m.llm_usage
        total = total + Usage(
            u.get("requests", 0), u.get("input_tokens", 0), u.get("output_tokens", 0)
        )
    return total


def estimate_input_tokens(system: str, turns: Sequence[Turn], tools: Sequence[ToolSpec]) -> int:
    """Rough upper estimate of input tokens from characters."""
    n = len(system)
    for t in turns:
        if isinstance(t, UserText):
            n += len(t.text)
        elif isinstance(t, AssistantTurn):
            n += len(str(t.response.raw))
        elif isinstance(t, ToolResults):
            n += sum(len(c) for _, c, _ in t.results)
    n += sum(len(x.description) + len(str(x.input_schema)) for x in tools)
    return n // CHARS_PER_TOKEN + 1


class BudgetGuard:
    """Tracks today's usage and refuses calls that could cross a cap."""

    def __init__(self, caps: Caps, already: Usage, recorder: RunRecorder | None = None) -> None:
        self.caps = caps
        self.already = already
        self.this_run = Usage()
        self.recorder = recorder

    @property
    def used(self) -> Usage:
        """Usage today including this run."""
        return self.already + self.this_run

    def check(self, input_estimate: int, max_output: int) -> None:
        """Raise BudgetExhausted unless one more call of this size fits."""
        u = self.used
        if u.requests + 1 > self.caps.max_requests_per_day:
            raise BudgetExhausted(f"request cap {self.caps.max_requests_per_day} reached")
        if u.total_tokens + input_estimate + max_output > self.caps.max_tokens_per_day:
            raise BudgetExhausted(
                f"token cap {self.caps.max_tokens_per_day} would be exceeded "
                f"(used {u.total_tokens}, next call up to {input_estimate + max_output})"
            )

    def record(self, usage: Usage) -> None:
        """Add the provider-reported usage of a finished call."""
        self.this_run = self.this_run + usage
        if self.recorder is not None:
            self.recorder.add_llm_usage(**usage.as_dict())


class GuardedLLM:
    """An `LLMClient` that enforces the caps; output tokens are capped per call."""

    def __init__(self, inner: LLMClient, guard: BudgetGuard) -> None:
        self.inner = inner
        self.guard = guard
        self.provider = inner.provider
        self.model = inner.model

    def sampling(self) -> dict[str, Any]:
        """See `LLMClient.sampling`."""
        return self.inner.sampling()

    def complete(
        self, system: str, turns: Sequence[Turn], *, max_tokens: int, tools: Sequence[ToolSpec] = ()
    ) -> LLMResponse:
        """Check the caps, call, record usage (also when the call fails after billing)."""
        out_cap = min(max_tokens, self.guard.caps.max_output_tokens)
        self.guard.check(estimate_input_tokens(system, turns, tools), out_cap)
        resp = self.inner.complete(system, turns, max_tokens=out_cap, tools=tools)
        self.guard.record(resp.usage)
        return resp
