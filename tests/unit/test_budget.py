from datetime import UTC, date, datetime

import pytest

from arena.clock import FixedClock
from arena.ledger import Ledger
from arena.ledger.manifest import run_manifest
from arena.llm.budget import (
    BudgetExhausted,
    BudgetGuard,
    Caps,
    GuardedLLM,
    usage_from_manifests,
)
from arena.llm.client import FakeLLM, Usage, UserText

CAPS = Caps(max_requests_per_day=3, max_tokens_per_day=1000, max_output_tokens=50, max_tool_calls=4)


def test_request_cap_stops_calls() -> None:
    llm = GuardedLLM(
        FakeLLM(["a", "b", "c", "d"], tokens_per_call=(10, 5)), BudgetGuard(CAPS, Usage())
    )
    for _ in range(3):
        llm.complete("s", [UserText("q")], max_tokens=400)
    with pytest.raises(BudgetExhausted, match="request cap"):
        llm.complete("s", [UserText("q")], max_tokens=400)
    assert llm.guard.used == Usage(3, 30, 15)


def test_token_cap_is_checked_before_the_call() -> None:
    fake = FakeLLM(["a"])
    llm = GuardedLLM(fake, BudgetGuard(CAPS, Usage(1, 900, 30)))
    with pytest.raises(BudgetExhausted, match="token cap"):
        llm.complete("s", [UserText("x" * 300)], max_tokens=400)
    assert fake.calls == []  # never called


def test_output_tokens_capped_per_call() -> None:
    seen = []

    class Spy(FakeLLM):
        def complete(self, system, turns, *, max_tokens, tools=()):
            seen.append(max_tokens)
            return super().complete(system, turns, max_tokens=max_tokens, tools=tools)

    GuardedLLM(Spy(["a"]), BudgetGuard(CAPS, Usage())).complete("s", [], max_tokens=9999)
    assert seen == [50]


def test_usage_summed_across_runs_of_the_day(tmp_path) -> None:
    led = Ledger(tmp_path)
    clock = FixedClock(datetime(2026, 11, 12, 6, tzinfo=UTC))
    for _ in range(2):
        with run_manifest(led, "morning", date(2026, 11, 12), clock) as rec:
            rec.add_llm_usage(requests=2, input_tokens=300, output_tokens=40)
    assert usage_from_manifests(led, date(2026, 11, 12)) == Usage(4, 600, 80)
    assert usage_from_manifests(led, date(2026, 11, 13)) == Usage()
    guard = BudgetGuard(Caps(4, 10_000, 50, 4), usage_from_manifests(led, date(2026, 11, 12)))
    with pytest.raises(BudgetExhausted):
        guard.check(10, 50)


def test_cached_and_reserved_usage_survives_restart(tmp_path) -> None:
    led = Ledger(tmp_path)
    clock = FixedClock(datetime(2026, 11, 12, 6, tzinfo=UTC))
    usage = Usage(2, 10, 5, 900, 100, reserved_tokens=40, unreported_requests=1)
    with run_manifest(led, "morning", date(2026, 11, 12), clock) as rec:
        rec.add_llm_usage(**usage.as_dict())
    assert usage_from_manifests(led, date(2026, 11, 12)) == usage
    guard = BudgetGuard(Caps(10, 1100, 50, 4), usage)
    with pytest.raises(BudgetExhausted, match="token cap"):
        guard.check(10, 50)


def test_refusal_usage_consumes_allowance_once(tmp_path) -> None:
    from arena.llm.client import LLMRefusal

    fake = FakeLLM([LLMRefusal("refused", usage=Usage(1, 123, 45))])
    with run_manifest(
        Ledger(tmp_path),
        "morning",
        date(2026, 11, 12),
        FixedClock(datetime(2026, 11, 12, 6, tzinfo=UTC)),
    ) as rec:
        guard = BudgetGuard(Caps(1, 10000, 50, 4), Usage(), rec)
        llm = GuardedLLM(fake, guard)
        with pytest.raises(LLMRefusal):
            llm.complete("s", [], max_tokens=50)
        with pytest.raises(BudgetExhausted, match="request cap"):
            llm.complete("s", [], max_tokens=50)
        assert guard.used == Usage(1, 123, 45)
        assert len(fake.calls) == 1
        assert rec.llm_usage == Usage(1, 123, 45).as_dict()


def test_unknown_usage_reserves_tokens_and_persists_failure(tmp_path) -> None:
    from arena.llm.client import LLMError

    led = Ledger(tmp_path)
    with (
        pytest.raises(LLMError),
        run_manifest(
            led,
            "morning",
            date(2026, 11, 12),
            FixedClock(datetime(2026, 11, 12, 6, tzinfo=UTC)),
        ) as rec,
    ):
        guard = BudgetGuard(CAPS, Usage(), rec)
        GuardedLLM(FakeLLM([LLMError("timeout")]), guard).complete("s", [], max_tokens=50)
    used = usage_from_manifests(led, date(2026, 11, 12))
    assert used.requests == used.unreported_requests == 1
    assert used.input_tokens == used.output_tokens == 0
    assert used.reserved_tokens == 51
