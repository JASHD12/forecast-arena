import json

import anthropic
import httpx2
import pytest

from arena.config import Settings
from arena.llm.anthropic_adapter import AnthropicLLM
from arena.llm.client import (
    AssistantTurn,
    FakeLLM,
    LLMError,
    LLMRefusal,
    ToolCall,
    ToolResults,
    ToolSpec,
    Usage,
    UserText,
    tool_reply,
)
from arena.llm.factory import client_from_settings
from arena.llm.openai_compatible import OpenAICompatibleLLM

TOOL = ToolSpec(
    "get_base_rate",
    "Base rate of a question",
    {
        "type": "object",
        "properties": {"question_id": {"type": "string"}},
        "required": ["question_id"],
        "additionalProperties": False,
    },
)


def anthropic_with(handler, effort=None) -> tuple[AnthropicLLM, list[dict]]:
    seen: list[dict] = []

    def h(request: httpx2.Request) -> httpx2.Response:
        seen.append(
            {
                "url": str(request.url),
                "headers": {k.lower(): v for k, v in request.headers.items()},
                "body": json.loads(request.content),
            }
        )
        return handler(request)

    sdk = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(h)),
    )
    return AnthropicLLM("claude-test", "unused", client=sdk, effort=effort), seen


def message(content, stop="end_turn"):
    return httpx2.Response(
        200,
        json={
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": "claude-test",
            "content": content,
            "stop_reason": stop,
            "stop_sequence": None,
            "usage": {"input_tokens": 123, "output_tokens": 45},
        },
    )


def test_anthropic_text_and_usage() -> None:
    llm, seen = anthropic_with(lambda r: message([{"type": "text", "text": '{"p": 1}'}]))
    r = llm.complete("SYS", [UserText("hello")], max_tokens=400)
    assert r.text == '{"p": 1}' and r.usage == Usage(1, 123, 45) and r.model == "claude-test"
    body = seen[0]["body"]
    assert seen[0]["url"].endswith("/v1/messages")
    assert body["system"] == "SYS" and body["max_tokens"] == 400
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert "temperature" not in body and "tools" not in body
    h = seen[0]["headers"]
    assert h.get("x-api-key") == "test-key" or h.get("authorization") == "Bearer test-key"
    assert "anthropic-version" in seen[0]["headers"]


def test_anthropic_tool_round_trip() -> None:
    llm, seen = anthropic_with(
        lambda r: message(
            [
                {
                    "type": "tool_use",
                    "id": "tu_1",
                    "name": "get_base_rate",
                    "input": {"question_id": "q1"},
                }
            ],
            stop="tool_use",
        )
    )
    r = llm.complete("S", [UserText("go")], max_tokens=100, tools=[TOOL])
    assert r.tool_calls == (ToolCall("tu_1", "get_base_rate", {"question_id": "q1"}),)
    assert seen[0]["body"]["tools"][0]["input_schema"]["required"] == ["question_id"]
    llm.complete(
        "S",
        [UserText("go"), AssistantTurn(r), ToolResults((("tu_1", "0.4", False),))],
        max_tokens=100,
        tools=[TOOL],
    )
    msgs = seen[1]["body"]["messages"]
    assert msgs[1]["role"] == "assistant" and msgs[1]["content"][0]["type"] == "tool_use"
    assert msgs[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "tu_1",
        "content": "0.4",
        "is_error": False,
    }


def test_anthropic_replays_thinking_blocks_unchanged() -> None:
    """Regression (2026-11-13 morning run): a truncated turn whose thinking block has a
    null field must be sent back exactly as received, or the API answers 400."""
    content = [
        {"type": "thinking", "thinking": "", "signature": "c2ln"},
        {"type": "thinking", "thinking": "", "signature": None, "new_field": {"k": 1}},
        {"type": "text", "text": '{"probability": 0.', "citations": None},
    ]
    llm, seen = anthropic_with(lambda r: message(content, stop="max_tokens"))
    r = llm.complete("S", [UserText("go")], max_tokens=400, tools=[TOOL])
    llm.complete(
        "S", [UserText("go"), AssistantTurn(r), UserText("repair")], max_tokens=400, tools=[TOOL]
    )
    assert seen[1]["body"]["messages"][1] == {"role": "assistant", "content": content}


def test_anthropic_refusal_and_errors() -> None:
    llm, _ = anthropic_with(lambda r: message([], stop="refusal"))
    with pytest.raises(LLMRefusal):
        llm.complete("S", [UserText("x")], max_tokens=10)
    llm, _ = anthropic_with(
        lambda r: httpx2.Response(
            429,
            json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}},
        )
    )
    with pytest.raises(LLMError, match="429"):
        llm.complete("S", [UserText("x")], max_tokens=10)


def oai(responses):
    seen = []

    def post(url, headers, body):
        seen.append((url, headers, json.loads(body)))
        return responses.pop(0)

    return OpenAICompatibleLLM("m-1", "k-1", "https://llm.example/v1", post=post), seen


def ok(msg, finish="stop"):
    return 200, json.dumps(
        {
            "model": "m-1",
            "choices": [{"index": 0, "message": msg, "finish_reason": finish, "logprobs": None}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 7},
        }
    ).encode()


def test_openai_compatible_text_tools_retry() -> None:
    llm, seen = oai([(503, b"busy"), ok({"role": "assistant", "content": "hi"})])
    r = llm.complete("S", [UserText("q")], max_tokens=300)
    assert r.text == "hi" and r.usage == Usage(1, 50, 7) and len(seen) == 2
    url, headers, body = seen[1]
    assert url == "https://llm.example/v1/chat/completions"
    assert headers["Authorization"] == "Bearer k-1"
    assert body["max_completion_tokens"] == 300 and body["temperature"] == 0.0
    assert body["messages"][0] == {"role": "system", "content": "S"}
    call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "get_base_rate", "arguments": '{"question_id": "q1"}'},
    }
    llm, seen = oai(
        [
            ok({"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls"),
            ok({"role": "assistant", "content": "done"}),
        ]
    )
    r = llm.complete("S", [UserText("q")], max_tokens=50, tools=[TOOL])
    assert r.tool_calls == (ToolCall("c1", "get_base_rate", {"question_id": "q1"}),)
    assert seen[0][2]["tools"][0]["function"]["parameters"]["required"] == ["question_id"]
    llm.complete(
        "S",
        [UserText("q"), AssistantTurn(r), ToolResults((("c1", "0.4", False),))],
        max_tokens=50,
        tools=[TOOL],
    )
    assert seen[1][2]["messages"][-1] == {"role": "tool", "tool_call_id": "c1", "content": "0.4"}


def test_openai_compatible_errors() -> None:
    llm, _ = oai([(401, b"no")])
    with pytest.raises(LLMError, match="401"):
        llm.complete("S", [UserText("q")], max_tokens=5)
    llm, _ = oai([(200, b"{}")])
    with pytest.raises(LLMError, match="malformed"):
        llm.complete("S", [UserText("q")], max_tokens=5)
    llm, _ = oai([ok({"role": "assistant", "content": ""}, "content_filter")])
    with pytest.raises(LLMRefusal):
        llm.complete("S", [UserText("q")], max_tokens=5)


def test_fake_llm_and_factory() -> None:
    fake = FakeLLM(["a", tool_reply(ToolCall("t", "x", {})), LLMError("boom")])
    assert fake.complete("s", [UserText("1")], max_tokens=5).text == "a"
    assert fake.complete("s", [], max_tokens=5).tool_calls[0].name == "x"
    with pytest.raises(LLMError):
        fake.complete("s", [], max_tokens=5)
    assert client_from_settings(Settings.from_env({})) is None
    s = Settings.from_env(
        {"ARENA_LLM_PROVIDER": "anthropic", "ARENA_LLM_MODEL": "m", "ARENA_LLM_API_KEY": "dummy"}
    )
    assert client_from_settings(s).provider == "anthropic"  # type: ignore[union-attr]
    assert "dummy" not in repr(s)


def test_anthropic_effort_sent_only_when_configured() -> None:
    llm, seen = anthropic_with(lambda r: message([{"type": "text", "text": "x"}]))
    llm.complete("SYS", [UserText("q")], max_tokens=400)
    assert "output_config" not in seen[0]["body"]
    assert llm.sampling()["effort"].startswith("provider default")
    llm2, seen2 = anthropic_with(lambda r: message([{"type": "text", "text": "x"}]), "low")
    llm2.complete("SYS", [UserText("q")], max_tokens=400)
    assert seen2[0]["body"]["output_config"] == {"effort": "low"}
    assert llm2.sampling()["effort"] == "low"
    assert "thinking" not in seen2[0]["body"] and "temperature" not in seen2[0]["body"]


def test_effort_setting_validated() -> None:
    import pytest

    from arena.config import Settings

    assert Settings.from_env({"ARENA_LLM_EFFORT": "low"}).llm_effort == "low"
    assert Settings.from_env({"ARENA_LLM_EFFORT": ""}).llm_effort is None
    with pytest.raises(ValueError):
        Settings.from_env({"ARENA_LLM_EFFORT": "turbo"})
