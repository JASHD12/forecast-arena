import os
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest
from power_fixtures import fixture_domain

from arena.domains.power import quantile, r0, r2
from arena.models import canonical_json

GOLDEN = Path(__file__).parents[1] / "fixtures" / "golden" / "power"
CASES = {
    "ordinary": date(2026, 11, 11),  # D = Thu 12 Nov 2026
    "spring_clock_change": date(2026, 3, 28),  # D = 29 Mar 2026, 23 hours
    "autumn_clock_change": date(2026, 10, 24),  # D = 25 Oct 2026, 25 hours
    "holiday": date(2025, 12, 24),  # D = Christmas Day
}


def generate(batch: date) -> str:
    asof = datetime.combine(batch, time(5, 30), tzinfo=UTC)
    return "".join(canonical_json(q) for q in fixture_domain().generate_questions(batch, asof))


@pytest.mark.parametrize("name", sorted(CASES))
def test_golden(name: str) -> None:
    path = GOLDEN / f"{name}.jsonl"
    got = generate(CASES[name])
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(got, encoding="utf-8")
    assert got == path.read_text(encoding="utf-8")


def test_deterministic_and_complete() -> None:
    batch = CASES["ordinary"]
    assert generate(batch) == generate(batch)
    asof = datetime.combine(batch, time(5, 30), tzinfo=UTC)
    qs = fixture_domain().generate_questions(batch, asof)
    assert {q.template for q in qs} == {
        "mean_gt", "max_gt", "min_lt", "spread_gt", "evening_gt", "up_vs_today"
    }
    for q in qs:
        assert q.target_date == date(2026, 11, 12)
        assert q.lock_time == datetime(2026, 11, 11, 9, 30, tzinfo=UTC)
        assert q.created_at <= q.lock_time
        assert "EUR/MWh" in q.text and "2026" in q.text and "Europe/Berlin" in q.text


def test_clock_change_hours_in_text() -> None:
    asof = datetime(2026, 3, 28, 5, 30, tzinfo=UTC)
    qs = fixture_domain().generate_questions(date(2026, 3, 28), asof)
    assert any("23 hours" in q.text for q in qs)
    asof = datetime(2026, 10, 24, 5, 30, tzinfo=UTC)
    qs = fixture_domain().generate_questions(date(2026, 10, 24), asof)
    assert any("25 hours" in q.text for q in qs)


def test_window_never_contains_target_or_future() -> None:
    batch = CASES["ordinary"]
    asof = datetime.combine(batch, time(5, 30), tzinfo=UTC)
    for q in fixture_domain().generate_questions(batch, asof):
        if "window_end" in q.params:
            assert date.fromisoformat(q.params["window_end"]) <= batch


def test_stale_data_skips_with_log() -> None:
    skips: list[str] = []
    asof = datetime(2026, 12, 20, 5, 30, tzinfo=UTC)
    assert fixture_domain(skips).generate_questions(date(2026, 12, 20), asof) == []
    assert any("stale" in s for s in skips)


def test_helpers() -> None:
    assert quantile([1, 2, 3, 4], 0.5) == 2.5
    assert quantile([5], 0.6) == 5
    assert r0(84.5) == 85 and r0(-0.5) == -1
    assert r2(1.005) == 1.01
