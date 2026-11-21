"""`llm_local_ft`: the QLoRA-fine-tuned open model as an experimental live forecaster (T271).

It reads exactly the `llm_context` prompt and answers with one calibrated probability from the
YES/NO logits (no text, so no parse failures and no rationale). Same daily sample and skip rules
as the other LLM forecasters; no silent fallback: a missing artefact, a failed load or a failed
call is a skip with its reason (integrity rule I6). The version carries the artefact hash and
the Platt coefficients, so any change is a new version (SPEC 8.5).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from arena.forecasters.llm import LLMContext
from arena.lab.artefacts import FtArtefact
from arena.lab.ft_runtime import Scorer, calibrated
from arena.llm import prompts
from arena.llm.client import LLMError
from arena.models import Forecast, Question, Skip


class LLMLocalFT(LLMContext):
    """The fine-tuned model; `scorer=None` records `model_missing` skips with `missing`."""

    forecaster_id = "llm_local_ft"

    def __init__(
        self,
        scorer: Scorer | None,
        artefact: FtArtefact | None,
        per_domain: int = 3,
        *,
        missing: str = "fine-tuned model not published yet",
    ) -> None:
        super().__init__(None, per_domain)
        self.scorer, self.artefact, self.missing = scorer, artefact, missing

    def version(self) -> str:
        """Artefact hash, Platt coefficients and prompt fingerprint."""
        fp = prompts.fingerprint(self.prompt_files, self.prompt_version)
        tag = f"prompt-{self.prompt_version}-{fp}"
        if self.artefact is None:
            return f"none|{tag}"
        return self.artefact.version(tag)

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        if self.scorer is None or self.artefact is None:
            return self._skip(q, "model_missing", self.missing, asof)
        if self.sample is not None and q.question_id not in self.sample:
            return self._skip(q, "not_sampled", "not in today's LLM sample", asof)
        system = prompts.load("system", self.prompt_version)
        try:
            margin = self.scorer.margin(system, self.user_prompt(q, ctx, asof))
        except LLMError as exc:
            return self._skip(q, "error", f"{type(exc).__name__}: {exc}", asof)
        return Forecast(
            forecast_id=f"{q.question_id}::{self.forecaster_id}",
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=self.version(),
            probability=calibrated(margin, self.artefact.platt),
            created_at=asof,
            meta={
                "model": self.scorer.model,
                "provider": "llama_cpp",
                "prompt_version": self.prompt_version,
                "margin": round(margin, 6),
                "platt": list(self.artefact.platt),
                "artefact_sha256": self.artefact.sha256,
                "experimental": True,
            },
        )
