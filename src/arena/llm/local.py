"""A local open-weights model as an `LLMClient` (T122, forecaster `llm_local`).

The model runs on the CPU of the GitHub runner through llama.cpp (`llama-cpp-python`),
so it costs nothing per call and is never counted against the API budget. Settings:
greedy decoding (temperature 0, fixed seed), output constrained by llama.cpp's JSON-schema
grammar to the answer contract of SPEC 9.2 (the parser still checks every answer), a time
limit per call (generation is stopped at the deadline and the call fails, so the
forecaster records an `error` skip, never a guess) and a total time budget per run.

Model: Qwen2.5-1.5B-Instruct, Q4_K_M GGUF, from the official Qwen repository on the
Hugging Face Hub (Apache-2.0, not gated), pinned to a revision.
"""

from __future__ import annotations

import time as _time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from arena.llm.client import (
    AssistantTurn,
    LLMError,
    LLMResponse,
    ToolResults,
    ToolSpec,
    Turn,
    Usage,
    UserText,
)

REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
REVISION = "91cad51170dc346986eccefdc2dd33a9da36ead9"
MODEL_ID = f"qwen2.5-1.5b-instruct-q4_k_m@{REVISION[:7]}"
SEED = 0
N_CTX = 4096

#: The SPEC 9.2 answer contract as a JSON schema (llama.cpp turns it into a grammar).
ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "probability": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string", "maxLength": 600},
        "key_factors": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
    },
    "required": ["probability", "rationale", "key_factors"],
    "additionalProperties": False,
}

#: (messages, max_tokens, stop) -> llama.cpp chat completion dict; injectable for tests.
Backend = Callable[[list[dict[str, str]], int, Callable[[], bool]], dict[str, Any]]


def model_path(cache_dir: Path) -> Path:
    """Download the pinned GGUF file once into `cache_dir` (plain HTTPS) and return it."""
    import os

    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    from huggingface_hub import hf_hub_download

    return Path(hf_hub_download(REPO, FILENAME, revision=REVISION, cache_dir=str(cache_dir)))


def llama_backend(path: Path, threads: int | None = None) -> Backend:
    """A backend around `llama_cpp.Llama` (loaded once). Streams the answer so generation
    can stop at the deadline between tokens; usage is approximate: prompt tokens from the
    model's tokenizer over the message texts, output tokens = streamed chunks."""
    from llama_cpp import Llama

    llm: Any = Llama(model_path=str(path), n_ctx=N_CTX, seed=SEED, n_threads=threads, verbose=False)

    def run(messages: list[dict[str, str]], max_tokens: int, stop: Callable[[], bool]) -> Any:
        stream = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.0,
            seed=SEED,
            response_format={"type": "json_object", "schema": ANSWER_SCHEMA},
            stream=True,
        )
        parts: list[str] = []
        finish = ""
        for chunk in stream:
            ch = chunk["choices"][0]
            parts.append(str(ch.get("delta", {}).get("content") or ""))
            finish = str(ch.get("finish_reason") or finish)
            if stop():
                break
        prompt = sum(len(llm.tokenize(m["content"].encode(), add_bos=False)) for m in messages)
        return {
            "choices": [{"message": {"content": "".join(parts)}, "finish_reason": finish}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": len(parts)},
        }

    return run


class LlamaCppLLM:
    """`LLMClient` over a local llama.cpp model (no tools, no API cost)."""

    provider = "llama_cpp"

    def __init__(
        self,
        backend: Backend,
        *,
        model: str = MODEL_ID,
        call_limit: float = 120.0,
        run_budget: float = 900.0,
        monotonic: Callable[[], float] = _time.monotonic,
    ) -> None:
        self.backend = backend
        self.model = model
        self.call_limit = call_limit
        self.run_budget = run_budget
        self.monotonic = monotonic
        self.spent = 0.0

    def sampling(self) -> dict[str, Any]:
        """Recorded on every forecast."""
        return {"temperature": 0.0, "seed": SEED, "grammar": "answer-json-schema",
                "call_limit_s": self.call_limit}  # fmt: skip

    def complete(
        self, system: str, turns: Sequence[Turn], *, max_tokens: int, tools: Sequence[ToolSpec] = ()
    ) -> LLMResponse:
        """See `LLMClient.complete`. Tools are not supported (llm_context uses none)."""
        if tools:
            raise LLMError("the local model is offered no tools")
        left = self.run_budget - self.spent
        if left <= 0:
            raise LLMError(f"local run time budget of {self.run_budget:.0f}s used up")
        limit = min(self.call_limit, left)
        msgs = [{"role": "system", "content": system}]
        for t in turns:
            if isinstance(t, UserText):
                msgs.append({"role": "user", "content": t.text})
            elif isinstance(t, AssistantTurn):
                msgs.append({"role": "assistant", "content": t.response.text})
            elif isinstance(t, ToolResults):
                raise LLMError("tool results cannot be sent to the local model")
        start = self.monotonic()
        timed_out = False

        def stop() -> bool:
            nonlocal timed_out
            timed_out = timed_out or self.monotonic() - start > limit
            return timed_out

        try:
            out = self.backend(msgs, max_tokens, stop)
        except LLMError:
            raise
        except Exception as exc:  # llama.cpp errors (context too long, ...)
            raise LLMError(f"local model failed: {type(exc).__name__}: {exc}") from exc
        finally:
            self.spent += self.monotonic() - start
        if timed_out:
            raise LLMError(f"local model hit the {limit:.0f}s time limit")
        try:
            choice = out["choices"][0]
            text = str(choice["message"]["content"] or "")
            u = out.get("usage") or {}
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected local response: {exc}") from exc
        return LLMResponse(
            text=text,
            tool_calls=(),
            stop_reason=str(choice.get("finish_reason") or ""),
            model=self.model,
            usage=Usage(1, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))),
        )
