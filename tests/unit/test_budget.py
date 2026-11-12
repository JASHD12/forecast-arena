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
