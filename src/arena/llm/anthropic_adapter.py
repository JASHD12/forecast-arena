"""Anthropic Messages API adapter, through the official `anthropic` SDK (2.x).

Written against the current API documentation (checked 2026-11-12, docs/SOURCES.md):
`client.messages.create(model, max_tokens, system, messages, tools)`; response content
blocks of type `text`, `thinking` and `tool_use`; `stop_reason` in end_turn, max_tokens,
stop_sequence, tool_use, pause_turn, refusal; `usage.input_tokens/output_tokens`.
Current models reject sampling parameters (`temperature` etc.), so none are sent and the
forecast records "provider default".

T190 (checked 2026-11-13 against the Claude API skill docs): `cache=True` sends top-level
`cache_control={"type": "ephemeral"}` (automatic prompt caching; minimum cacheable prefix
on Claude Haiku 5.5 is 512 tokens) and reads `usage.cache_read_input_tokens` /
`cache_creation_input_tokens`. `structured=True` sends `output_config.format` with the
answer JSON Schema on calls without tools, so the answer is schema-valid by construction;
it changes the output contract, so it is part of `sampling()` and of forecaster versions.

Server-side refusal fallbacks are deliberately not enabled: a forecast must be
attributable to exactly one model id.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import anthropic

from arena.llm.client import (
    AssistantTurn,
    LLMError,
    LLMRefusal,
    LLMResponse,
    ToolCall,
    ToolResults,
    ToolSpec,
    Turn,
    Usage,
    UserText,
)
from arena.llm.parse import ANSWER_SCHEMA

#: Pinned so that only ARENA_* settings configure the client (an ambient
#: ANTHROPIC_BASE_URL is ignored).
BASE_URL = "https://api.anthropic.com"


class AnthropicLLM:
    """`LLMClient` for the Anthropic Messages API."""

    provider = "anthropic"

    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        client: anthropic.Anthropic | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        effort: str | None = None,
        cache: bool = False,
        structured: bool = False,
    ) -> None:
        self.model = model
        self.effort = effort
        self.cache = cache
        self.structured = structured
        self.client = client or anthropic.Anthropic(
            base_url=BASE_URL, api_key=api_key, timeout=timeout, max_retries=max_retries
        )

    def sampling(self) -> dict[str, Any]:
        """No sampling parameters are sent (rejected by current models); the effort level
        is recorded when one is configured."""
        out: dict[str, Any] = {"temperature": "provider default (not sent)"}
        out["effort"] = self.effort or "provider default (not sent)"
        out["output_format"] = "json_schema" if self.structured else "text"
        out["prompt_cache"] = "auto" if self.cache else "off"
        return out

    @staticmethod
    def to_messages(turns: Sequence[Turn]) -> list[dict[str, Any]]:
        """Neutral turns -> Messages API `messages`."""
        out: list[dict[str, Any]] = []
        for t in turns:
            if isinstance(t, UserText):
                out.append({"role": "user", "content": t.text})
            elif isinstance(t, AssistantTurn):
                out.append({"role": "assistant", "content": t.response.raw})
            elif isinstance(t, ToolResults):
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": cid,
                                "content": content,
                                "is_error": err,
                            }
                            for cid, content, err in t.results
                        ],
                    }
                )
        return out

    def complete(
        self, system: str, turns: Sequence[Turn], *, max_tokens: int, tools: Sequence[ToolSpec] = ()
    ) -> LLMResponse:
        """See `LLMClient.complete`."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": self.to_messages(turns),
        }
        output_config: dict[str, Any] = {}
        if self.effort:
            output_config["effort"] = self.effort
        if self.structured and not tools:
            output_config["format"] = {"type": "json_schema", "schema": ANSWER_SCHEMA}
        if output_config:
            kwargs["output_config"] = output_config
        if self.cache:
            kwargs["cache_control"] = {"type": "ephemeral"}
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]
        try:
            msg = self.client.messages.create(**kwargs)
        except anthropic.APIStatusError as exc:
            raise LLMError(f"anthropic HTTP {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError(f"anthropic connection error: {exc}") from exc
        u = msg.usage
        usage = Usage(
            1,
            int(u.input_tokens),
            int(u.output_tokens),
            int(getattr(u, "cache_read_input_tokens", None) or 0),
            int(getattr(u, "cache_creation_input_tokens", None) or 0),
        )
        if msg.stop_reason == "refusal":
            raise LLMRefusal(f"model declined (usage {usage.as_dict()})")
        text = "".join(b.text for b in msg.content if b.type == "text")
        calls = tuple(
            ToolCall(b.id, b.name, dict(b.input)) for b in msg.content if b.type == "tool_use"
        )
        # Re-sent byte for byte in later turns: thinking blocks must come back unchanged
        # (with tools, the API rejects a modified one). `to_dict()` keeps fields exactly as
        # received, including nulls and fields this SDK version does not know;
        # `model_dump(exclude_none=True)` dropped a null and broke the agent (2026-11-13).
        raw = [b.to_dict() for b in msg.content]
        resp = LLMResponse(text, calls, str(msg.stop_reason), str(msg.model), usage, raw)
        return resp
