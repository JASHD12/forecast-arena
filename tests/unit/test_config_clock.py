from datetime import UTC, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

from arena.clock import FixedClock, SystemClock, ensure_utc
from arena.config import Settings


def test_defaults() -> None:
    s = Settings.from_env({})
    assert s.llm_max_requests_per_day == 100
    assert s.llm_max_tokens_per_day == 400_000
    assert s.llm_max_output_tokens == 400
    assert s.agent_max_tool_calls == 4
    assert s.llm_questions_per_domain == 3
    assert s.lock_time_utc == time(9, 30)
    assert s.ledger_dir == Path("_ledger")
    assert not s.llm_configured


def test_overrides_and_unrelated_env_ignored() -> None:
    s = Settings.from_env(
        {
            "ARENA_LLM_MAX_REQUESTS_PER_DAY": "7",
            "ARENA_DOMAINS": "power, weather",
            "ARENA_CONTACT": "me@example.org",
            "HOME": "/root",
        }
    )
    assert s.llm_max_requests_per_day == 7
    assert s.domains == ("power", "weather")
    assert "me@example.org" in s.user_agent()


def test_secret_not_in_repr() -> None:
    s = Settings.from_env(
        {"ARENA_LLM_API_KEY": "sk-test-123", "ARENA_LLM_PROVIDER": "x", "ARENA_LLM_MODEL": "m"}
    )
    assert s.llm_configured
    assert "sk-test-123" not in repr(s)
    assert "sk-test-123" not in s.model_dump_json()


def test_empty_strings_are_unset_and_unknown_keys_fail() -> None:
    assert Settings.from_env({"ARENA_LLM_MODEL": " "}).llm_model is None
    with pytest.raises(ValueError, match="unknown setting"):
        Settings.from_env({"ARENA_NOPE": "1"})


def test_user_agent_falls_back_to_repo() -> None:
    assert Settings.from_env({}).repo_url in Settings.from_env({}).user_agent()


def test_fixed_clock() -> None:
    c = FixedClock(datetime(2026, 3, 29, 1, 0, tzinfo=UTC))
    assert c.now() == datetime(2026, 3, 29, 1, 0, tzinfo=UTC)
    c.advance(timedelta(hours=2))
    assert c.now().hour == 3
    with pytest.raises(ValueError):
        c.advance(timedelta(seconds=-1))


def test_clock_normalises_to_utc_and_refuses_naive() -> None:
    cet = timezone(timedelta(hours=1))
    assert FixedClock(datetime(2026, 1, 1, 10, tzinfo=cet)).now().hour == 9
    with pytest.raises(ValueError):
        ensure_utc(datetime(2026, 1, 1))
    assert SystemClock().now().tzinfo is not None
