"""Self-consistency for `llm_context` (T298, evaluation variant): ask k times, average.

The same prompt is sent `K` times; the answers come from the provider's default sampling (current
models reject a temperature parameter, see `llm/anthropic_adapter.py`), so they differ, and the mean
probability is the forecast. The spread of the answers is recorded. At least `MIN_OK` answers must
parse, otherwise the question is a skip with the reason (I6). It costs `K` times the tokens of
`llm_context`, so it is an evaluation variant (`arena eval run`), not a live forecaster.
"""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any

from arena.forecasters.llm import LLMContext
from arena.models import Forecast, Question, Skip

K = 5
MIN_OK = 3


class SelfConsistency(LLMContext):
    """`llm_context` sampled `K` times with the probabilities averaged."""

    forecaster_id = "llm_context_sc5"

    def version(self) -> str:
        """The base version plus the sampling rule (SPEC 8.5)."""
        return f"{super().version()}|selfcons-k{K}-mean"

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        answers: list[Forecast] = []
        last: Skip | None = None
        for _ in range(K):
            r = super().forecast(q, ctx, asof)
            if isinstance(r, Forecast):
                answers.append(r)
            else:
                last = r
                if r.reason_code in ("not_sampled", "model_missing", "budget_exhausted"):
                    return self._skip(q, r.reason_code, r.detail, asof)  # no point in asking again
        if len(answers) < MIN_OK:
            detail = f"{len(answers)} of {K} answers usable" + (
                f"; last: {last.detail}" if last else ""
            )
            return self._skip(
                q,
                "error" if last and last.reason_code == "error" else "parse_failure",
                detail,
                asof,
            )
        probs = [a.probability for a in answers]
        first = answers[0]
        return Forecast(
            forecast_id=f"{q.question_id}::{self.forecaster_id}",
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=self.version(),
            probability=sum(probs) / len(probs),
            created_at=asof,
            rationale=first.rationale,
            meta={
                **first.meta,
                "self_consistency": {
                    "k": K,
                    "answers": [round(p, 4) for p in probs],
                    "spread_sd": round(statistics.pstdev(probs), 4),
                },
            },
        )
