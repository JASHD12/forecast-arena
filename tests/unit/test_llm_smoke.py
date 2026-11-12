from click.testing import CliRunner

from arena.cli import main
from arena.llm.client import FakeLLM, LLMError, ToolCall, tool_reply
from arena.llm.smoke import run_smoke

GOOD = '{"probability": 0.99, "rationale": "The sun rises daily.", "key_factors": ["astronomy"]}'


def test_two_calls_and_usage_reported() -> None:
    fake = FakeLLM([GOOD, tool_reply(ToolCall("t1", "get_utc_date", {}))])
    res = run_smoke(fake, 400)
    assert res.ok
    assert len(fake.calls) == 2
    assert fake.calls[1][2][0].name == "get_utc_date"
    assert res.usage.requests == 2
    text = "\n".join(res.lines)
    assert "contract ok" in text and "get_utc_date" in text and "total usage" in text


def test_contract_violation_and_errors_fail_without_raising() -> None:
    res = run_smoke(FakeLLM(["probably yes", LLMError("HTTP 401")]), 400)
    assert not res.ok
    text = "\n".join(res.lines)
    assert "violates the output contract" in text and "call 2 failed" in text


def test_cli_refuses_outside_actions(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    res = CliRunner().invoke(main, ["llm", "smoke"])
    assert res.exit_code == 2 and "only inside GitHub Actions" in res.output


def test_cli_reports_model_missing(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    for k in ("ARENA_LLM_PROVIDER", "ARENA_LLM_MODEL", "ARENA_LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    res = CliRunner().invoke(main, ["llm", "smoke"])
    assert res.exit_code == 1 and "model_missing" in res.output
