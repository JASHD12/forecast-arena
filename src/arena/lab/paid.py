"""Shared plumbing for the small paid lab runs (T247, T250, T252b, T298).

Owner approval: HUMAN_TODO H27, H31, H36.

Every paid lab run goes through `PaidRun`: a `GuardedLLM` with hard request and token caps for
this run only, usage added up from the provider's own fields, and the cost computed with the
price table of the LLM observability page. Live calls run only inside GitHub Actions (S8). The
tests use `FakeLLM`.
"""

from __future__ import annotations

import os
from typing import Any

from arena.llm.budget import BudgetGuard, Caps, GuardedLLM
from arena.llm.client import LLMClient, LLMResponse, Usage, UserText
from arena.site.llm_obs import price_for


def in_actions() -> bool:
    """True inside GitHub Actions (live LLM calls are refused anywhere else, rule S8)."""
    return os.environ.get("GITHUB_ACTIONS") == "true"


class PaidRun:
    """One capped, accounted sequence of model calls."""

    def __init__(
        self, client: LLMClient, *, max_requests: int, max_tokens: int, max_output_tokens: int
    ) -> None:
        self.client = client
        self.guard = BudgetGuard(Caps(max_requests, max_tokens, max_output_tokens, 0), Usage())
        self.llm = GuardedLLM(client, self.guard)
        self.max_output_tokens = max_output_tokens

    def ask(self, system: str, user: str, max_tokens: int | None = None) -> LLMResponse:
        """One request; raises `BudgetExhausted` or `LLMError` (the caller records the skip)."""
        return self.llm.complete(
            system, [UserText(user)], max_tokens=max_tokens or self.max_output_tokens
        )

    @property
    def usage(self) -> Usage:
        """Usage of this run so far."""
        return self.guard.this_run

    def cost_usd(self) -> float | None:
        """List-price cost of this run, None if the model has no known price."""
        price = price_for(self.client.provider, self.client.model)
        if price is None:
            return None
        u = self.usage
        return round((u.input_tokens * price[0] + u.output_tokens * price[1]) / 1e6, 4)

    def summary(self) -> dict[str, Any]:
        """Usage and cost for the log and the result file."""
        return {
            "usage": self.usage.as_dict(),
            "cost_usd": self.cost_usd(),
            "model": self.client.model,
        }
