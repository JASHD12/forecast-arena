"""`llm_plain` and `llm_context` (SPEC 8.4, 9.2) and the shared daily sample.

Each day a seeded, stratified sample of `ARENA_LLM_QUESTIONS_PER_DOMAIN` questions per
domain is drawn from the batch; every LLM forecaster answers exactly that sample so the
comparison is paired. Questions outside the sample get a `not_sampled` skip.

Failure handling never produces a number: a missing client is `model_missing`, a cap is
`budget_exhausted`, two unparseable answers are `parse_failure`, a provider error or a
refusal is `error`.
"""

from __future__ import annotations

import json
import random
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from arena.llm import prompts
from arena.llm.budget import BudgetExhausted
from arena.llm.client import AssistantTurn, LLMClient, LLMError, LLMResponse, Turn, Usage, UserText
from arena.llm.parse import Answer, ParseError, parse_answer
from arena.models import Forecast, Question, Skip

CONTEXT_CHARS = 6000


def daily_sample(questions: Sequence[Question], per_domain: int) -> set[str]:
    """Seeded (by batch date) sample of `per_domain` question ids per domain, stratified
    by template: templates are visited in a seeded order, one question each, round-robin."""
    out: set[str] = set()
    by_domain: dict[str, list[Question]] = {}
    for q in questions:
        by_domain.setdefault(q.domain, []).append(q)
    for domain, qs in sorted(by_domain.items()):
        batch = min(q.batch_date for q in qs)
        rng = random.Random(f"llm-sample-{domain}-{batch.isoformat()}")
        by_t: dict[str, list[Question]] = {}
        for q in sorted(qs, key=lambda x: x.question_id):
            by_t.setdefault(q.template, []).append(q)
        for lst in by_t.values():
            rng.shuffle(lst)
        order = sorted(by_t)
        rng.shuffle(order)
        picked: list[str] = []
        while len(picked) < per_domain and any(by_t.values()):
            for t in order:
                if by_t[t] and len(picked) < per_domain:
                    picked.append(by_t[t].pop().question_id)
        out.update(picked)
    return out


def render_context(ctx: dict[str, Any], limit: int = CONTEXT_CHARS) -> str:
    """Compact JSON rendering of the as-of context, truncated to `limit` characters."""
    text = json.dumps(ctx, sort_keys=True, separators=(",", ":"), default=str)
    return text if len(text) <= limit else text[:limit] + " ...(truncated)"


class LLMForecaster:
    """Base for the sampled LLM forecasters."""

    forecaster_id = "llm"
    max_output_tokens = 400
    prompt_files: tuple[str, ...] = ("system", "repair")

    def __init__(
        self,
        client: LLMClient | None,
        per_domain: int = 3,
        prompt_version: str = prompts.PROMPT_VERSION,
    ) -> None:
        self.client = client
        self.per_domain = per_domain
        self.prompt_version = prompt_version
        self.sample: set[str] | None = None

    def prepare(self, questions: Sequence[Question]) -> None:
        """Called by the morning job with the whole batch before forecasting."""
        self.sample = daily_sample(questions, self.per_domain)

    def version(self) -> str:
        """Model id and prompt version (SPEC 8.5)."""
        model = self.client.model if self.client is not None else "none"
        fp = prompts.fingerprint(self.prompt_files, self.prompt_version)
        return f"{model}|prompt-{self.prompt_version}-{fp}|out-{self.max_output_tokens}"

    def user_prompt(self, q: Question, ctx: dict[str, Any], asof: datetime) -> str:
        """The first user message."""
        raise NotImplementedError

    def _skip(self, q: Question, reason: str, detail: str, asof: datetime) -> Skip:
        return Skip(
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=self.version(),
            reason_code=reason,  # type: ignore[arg-type]
            detail=detail[:300],
            created_at=asof,
        )

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        if self.client is None:
            return self._skip(q, "model_missing", "no LLM configured", asof)
        if self.sample is not None and q.question_id not in self.sample:
            return self._skip(q, "not_sampled", "not in today's LLM sample", asof)
        system = prompts.load("system", self.prompt_version)
        turns: list[Turn] = [UserText(self.user_prompt(q, ctx, asof))]
        usage = Usage()
        try:
            answer, resp, usage = self._ask(system, turns, usage)
        except BudgetExhausted as exc:
            return self._skip(q, "budget_exhausted", str(exc), asof)
        except LLMError as exc:
            return self._skip(q, "error", f"{type(exc).__name__}: {exc}", asof)
        except ParseError as exc:
            return self._skip(q, "parse_failure", f"two unparseable answers: {exc}", asof)
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
            },
        )

    def _ask(
        self, system: str, turns: list[Turn], usage: Usage
    ) -> tuple[Answer, LLMResponse, Usage]:
        """One call plus at most one repair retry."""
        assert self.client is not None
        resp = self.client.complete(system, turns, max_tokens=self.max_output_tokens)
        usage = usage + resp.usage
        try:
            return parse_answer(resp.text), resp, usage
        except ParseError as first:
            repair = prompts.load("repair", self.prompt_version).replace("{error}", str(first))
            turns = [*turns, AssistantTurn(resp), UserText(repair)]
            resp = self.client.complete(system, turns, max_tokens=self.max_output_tokens)
            usage = usage + resp.usage
            return parse_answer(resp.text), resp, usage


class LLMPlain(LLMForecaster):
    """Question text, resolution rule and the current date only. No data, no tools."""

    forecaster_id = "llm_plain"
    prompt_files = ("system", "repair", "plain_user")

    def user_prompt(self, q: Question, ctx: dict[str, Any], asof: datetime) -> str:
        """See `LLMForecaster.user_prompt`."""
        return (
            prompts.load("plain_user", self.prompt_version)
            .replace("{today}", asof.date().isoformat())
            .replace("{lock_time}", q.lock_time.strftime("%Y-%m-%d %H:%M UTC"))
            .replace("{question}", q.text)
            .replace("{rule}", q.resolution_rule)
        )


class LLMContext(LLMForecaster):
    """As `llm_plain`, plus a compact rendering of the as-of context."""

    forecaster_id = "llm_context"
    prompt_files = ("system", "repair", "context_user")

    def user_prompt(self, q: Question, ctx: dict[str, Any], asof: datetime) -> str:
        """See `LLMForecaster.user_prompt`."""
        return (
            prompts.load("context_user", self.prompt_version)
            .replace("{today}", asof.date().isoformat())
            .replace("{lock_time}", q.lock_time.strftime("%Y-%m-%d %H:%M UTC"))
            .replace("{question}", q.text)
            .replace("{rule}", q.resolution_rule)
            .replace("{asof}", asof.strftime("%Y-%m-%d %H:%M UTC"))
            .replace("{context}", render_context(ctx))
        )


class LLMLocal(LLMContext):
    """`llm_local` (SPEC 8.8): exactly `llm_context`'s prompts and contract, answered by an
    open-weights model running locally on the CPU (`arena.llm.local`), at no API cost."""

    forecaster_id = "llm_local"

    def __init__(
        self,
        client: LLMClient | None,
        per_domain: int = 3,
        *,
        missing: str = "no local model configured",
    ) -> None:
        super().__init__(client, per_domain)
        self.missing = missing

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """As `llm_context`; without a model, the skip says why it is missing."""
        if self.client is None:
            return self._skip(q, "model_missing", self.missing, asof)
        return super().forecast(q, ctx, asof)
