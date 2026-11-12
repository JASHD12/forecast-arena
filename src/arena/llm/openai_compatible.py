"""OpenAI-compatible chat-completions adapter (raw HTTP; many providers and local servers).

Written against OpenAI's published OpenAPI spec (github.com/openai/openai-openapi,
checked 2026-11-12, docs/SOURCES.md): `POST {base}/chat/completions` with `model`,
`messages` (system/user/assistant/tool; tool messages need `tool_call_id`),
`max_completion_tokens` (`max_tokens` is deprecated), `temperature` (0-2) and function
`tools`; response `choices[0].message` (`content`, `tool_calls[].function.arguments` as a
JSON string), `finish_reason`, and `usage.prompt_tokens/completion_tokens`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

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
from arena.sources.http import HttpError

Post = Callable[[str, dict[str, str], bytes], tuple[int, bytes]]


def urllib_post(
    url: str, headers: dict[str, str], body: bytes, timeout: float = 60.0
) -> tuple[int, bytes]:
    """POST with the standard library; returns (status, body)."""
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() or b""


class OpenAICompatibleLLM:
    """`LLMClient` for `/chat/completions` endpoints."""

    provider = "openai_compatible"

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        *,
        temperature: float = 0.0,
        post: Post = urllib_post,
        retries: int = 2,
    ) -> None:
        if not base_url:
            raise ValueError("ARENA_LLM_BASE_URL is required for openai_compatible")
        self.model = model
        self.api_key = api_key
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.temperature = temperature
        self.post = post
        self.retries = retries

    def sampling(self) -> dict[str, Any]:
        """Temperature actually sent."""
        return {"temperature": self.temperature}

    @staticmethod
    def to_messages(system: str, turns: Sequence[Turn]) -> list[dict[str, Any]]:
        """Neutral turns -> chat-completions `messages`."""
        out: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for t in turns:
            if isinstance(t, UserText):
                out.append({"role": "user", "content": t.text})
            elif isinstance(t, AssistantTurn):
                out.append(t.response.raw)
            elif isinstance(t, ToolResults):
                for cid, content, err in t.results:
                    out.append(
                        {
                            "role": "tool",
                            "tool_call_id": cid,
                            "content": ("ERROR: " if err else "") + content,
                        }
                    )
        return out

    def complete(
        self, system: str, turns: Sequence[Turn], *, max_tokens: int, tools: Sequence[ToolSpec] = ()
    ) -> LLMResponse:
        """See `LLMClient.complete`."""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": self.to_messages(system, turns),
            "max_completion_tokens": max_tokens,
            "temperature": self.temperature,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        data = json.dumps(body).encode()
        status, raw = 0, b""
        for _ in range(self.retries + 1):
            try:
                status, raw = self.post(self.url, headers, data)
            except (OSError, TimeoutError, HttpError) as exc:
                status, raw = 0, str(exc).encode()
                continue
            if status not in (408, 409, 429) and status < 500:
                break
        if status != 200:
            raise LLMError(f"openai_compatible HTTP {status}: {raw[:200]!r}")
        try:
            doc = json.loads(raw)
            choice = doc["choices"][0]
            msg = choice["message"]
            u = doc.get("usage") or {}
            usage = Usage(1, int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)))
            calls = []
            for tc in msg.get("tool_calls") or []:
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {"_unparseable_arguments": tc["function"]["arguments"]}
                calls.append(ToolCall(tc["id"], tc["function"]["name"], args))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(f"malformed chat-completions response: {exc}") from exc
        if choice.get("finish_reason") == "content_filter":
            raise LLMRefusal("content filtered by the provider")
        raw_msg = {"role": "assistant", "content": msg.get("content")}
        if msg.get("tool_calls"):
            raw_msg["tool_calls"] = msg["tool_calls"]
        return LLMResponse(
            msg.get("content") or "",
            tuple(calls),
            str(choice.get("finish_reason")),
            str(doc.get("model", self.model)),
            usage,
            raw_msg,
        )
