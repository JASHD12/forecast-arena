"""Running the fine-tuned model on the runner CPU through llama.cpp (T271).

The model answers with one token: the logits of `YES` and `NO` at the start of the assistant
answer give the margin logit(YES) - logit(NO); a Platt map fitted on the validation split turns
it into a probability. The prompt text is the same ChatML text the training code built with the
Qwen tokenizer's chat template (checked by a unit test on the template and by the parity
command against the fp16 model).
"""

from __future__ import annotations

import math
import time as _time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from arena.llm.client import LLMError


class Scorer(Protocol):
    """Anything that turns (system, user) into the margin logit(YES) - logit(NO)."""

    model: str

    def margin(self, system: str, user: str) -> float: ...


def chatml(system: str, user: str) -> str:
    """The Qwen2.5 chat text up to the start of the assistant answer."""
    return (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


def sigmoid(x: float) -> float:
    """Numerically safe logistic function."""
    return 1 / (1 + math.exp(-x)) if x >= 0 else math.exp(x) / (1 + math.exp(x))


def calibrated(margin: float, platt: tuple[float, float]) -> float:
    """Platt map P = sigmoid(a * margin + b), clipped to [0.01, 0.99] like the scoring code."""
    a, b = platt
    return min(0.99, max(0.01, sigmoid(a * margin + b)))


class LlamaScorer:
    """Margins from a GGUF file with `llama_cpp.Llama` (loaded once; CPU)."""

    def __init__(
        self,
        path: Path,
        *,
        model: str,
        yes_id: int,
        no_id: int,
        threads: int | None = None,
        run_budget: float = 1800.0,
        n_ctx: int = 4096,
        monotonic: Callable[[], float] = _time.monotonic,
    ) -> None:
        from llama_cpp import Llama

        self.model = model
        self.llm: Any = Llama(
            model_path=str(path), n_ctx=n_ctx, seed=0, n_threads=threads, verbose=False
        )
        yes = self.llm.tokenize(b"YES", add_bos=False)
        no = self.llm.tokenize(b"NO", add_bos=False)
        if yes != [yes_id] or no != [no_id]:
            raise ValueError(f"YES/NO token ids differ from the pin: {yes}, {no}")
        self.yes_id, self.no_id = yes_id, no_id
        self.run_budget, self.spent, self.monotonic = run_budget, 0.0, monotonic
        self.n_ctx = n_ctx

    def margin(self, system: str, user: str) -> float:
        """logit(YES) - logit(NO) for one prompt; raises `LLMError` past the run budget."""
        if self.spent >= self.run_budget:
            raise LLMError(f"local run time budget of {self.run_budget:.0f}s used up")
        start = self.monotonic()
        tokens = self.llm.tokenize(chatml(system, user).encode(), add_bos=False, special=True)
        if len(tokens) >= self.n_ctx:
            raise LLMError(f"prompt of {len(tokens)} tokens does not fit the context")
        self.llm.reset()
        self.llm.eval(tokens)
        logits = self.llm.scores[self.llm.n_tokens - 1]
        value = float(logits[self.yes_id] - logits[self.no_id])
        self.spent += self.monotonic() - start
        if not math.isfinite(value):
            raise LLMError("non-finite logits")
        return value
