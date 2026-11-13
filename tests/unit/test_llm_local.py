"""`llm_local` (T122): the local llama.cpp client, tested with a fake backend."""

import json
from datetime import UTC, datetime

import pytest
from factories import question

from arena.forecasters.llm import LLMContext, LLMLocal
from arena.llm.client import LLMError, ToolSpec, UserText
from arena.llm.local import ANSWER_SCHEMA, MODEL_ID, LlamaCppLLM
from arena.llm.parse import KEYS
from arena.models import Forecast, Skip

ASOF = datetime(2026, 11, 12, 6, tzinfo=UTC)
GOOD = json.dumps({"probability": 0.3, "rationale": "Trend down.", "key_factors": ["trend"]})


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def backend(texts, clock=None, step=0.0):
    """Returns the scripted texts in order; each call advances the clock by `step`."""
    seen = []

    def run(messages, max_tokens, stop):
        seen.append(messages)
        if clock is not None:
            clock.t += step
        stop()
        return {"choices": [{"message": {"content": texts[len(seen) - 1]},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 500, "completion_tokens": 40}}  # fmt: skip

    run.seen = seen  # type: ignore[attr-defined]
    return run


def test_schema_matches_the_answer_contract() -> None:
    assert set(ANSWER_SCHEMA["required"]) == KEYS
    assert ANSWER_SCHEMA["additionalProperties"] is False


def test_same_prompts_as_llm_context_and_a_forecast() -> None:
    b = backend([GOOD])
    f = LLMLocal(LlamaCppLLM(b))
    ctx = {"daily": [{"day": "2026-11-11", "mean": 80.0}]}
    out = f.forecast(question(), ctx, ASOF)
    assert isinstance(out, Forecast) and out.forecaster_id == "llm_local"
    assert out.probability == 0.3 and out.meta["provider"] == "llama_cpp"
    assert out.forecaster_version.startswith(MODEL_ID)
    assert out.meta["usage"] == {"requests": 1, "input_tokens": 500, "output_tokens": 40}
    (msgs,) = b.seen  # type: ignore[attr-defined]
    expected = LLMContext(None).user_prompt(question(), ctx, ASOF)
    assert [m["role"] for m in msgs] == ["system", "user"] and msgs[1]["content"] == expected


def test_repair_then_parse_failure_skip() -> None:
    f = LLMLocal(LlamaCppLLM(backend(["nope", "still nope"])))
    out = f.forecast(question(), {}, ASOF)
    assert isinstance(out, Skip) and out.reason_code == "parse_failure"


def test_time_limit_and_run_budget_become_error_skips() -> None:
    clock = Clock()
    client = LlamaCppLLM(backend([GOOD, GOOD, GOOD], clock, step=30), call_limit=20,
                         run_budget=50, monotonic=clock)  # fmt: skip
    f = LLMLocal(client)
    slow = f.forecast(question(), {}, ASOF)
    assert isinstance(slow, Skip) and slow.reason_code == "error" and "time limit" in slow.detail
    client.call_limit = 100
    f.forecast(question(), {}, ASOF)  # uses 30 s more: 60 > 50
    over = f.forecast(question(), {}, ASOF)
    assert isinstance(over, Skip) and "budget" in over.detail


def test_backend_errors_and_tools_are_refused() -> None:
    def broken(messages, max_tokens, stop):
        raise ValueError("context window exceeded")

    with pytest.raises(LLMError, match="context window"):
        LlamaCppLLM(broken).complete("s", [UserText("u")], max_tokens=10)
    with pytest.raises(LLMError, match="no tools"):
        LlamaCppLLM(backend([GOOD])).complete(
            "s", [UserText("u")], max_tokens=10, tools=[ToolSpec("t", "d", {})]
        )
    assert LlamaCppLLM(backend([GOOD])).sampling()["temperature"] == 0.0


def test_wiring_builds_llm_local_when_switched_on(tmp_path, monkeypatch) -> None:
    from factories import B

    from arena.config import Settings
    from arena.ledger import Ledger
    from arena.llm import local
    from arena.ops.wiring import build_forecasters

    monkeypatch.setattr(local, "model_path", lambda d: tmp_path / "m.gguf")
    monkeypatch.setattr(local, "llama_backend", lambda p: backend([GOOD]))
    s = Settings.from_env({"ARENA_LLM_LOCAL": "1"})
    fs, guard = build_forecasters(Ledger(tmp_path), [], s, B, dry_run=True)
    (loc,) = [f for f in fs if f.forecaster_id == "llm_local"]
    assert loc.client is not None and guard is None  # runs in dry runs, outside the API guard


def test_a_failed_load_records_model_missing_with_the_reason(tmp_path, monkeypatch) -> None:
    from factories import B

    from arena.config import Settings
    from arena.ledger import Ledger
    from arena.llm import local
    from arena.ops.wiring import build_forecasters

    def fail(d):
        raise ImportError("No module named 'llama_cpp'")

    monkeypatch.setattr(local, "model_path", fail)
    fs, _ = build_forecasters(Ledger(tmp_path), [], Settings.from_env({"ARENA_LLM_LOCAL": "1"}), B)
    (loc,) = [f for f in fs if f.forecaster_id == "llm_local"]
    out = loc.forecast(question(), {}, ASOF)
    assert (
        isinstance(out, Skip) and out.reason_code == "model_missing" and "llama_cpp" in out.detail
    )
