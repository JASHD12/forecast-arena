"""Backtest of `sentiment-gdelt-r1` (T374): loading, as-of discipline, no leakage, rules."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from crypto_fixtures import fixture_crypto

from arena.backtest import sentiment as B
from arena.forecasters import sentiment as S

HISTORY = Path(__file__).parents[1] / "fixtures" / "gdelt" / "history"


def test_load_news_marks_recorded_days_only() -> None:
    news = B.load_news(HISTORY)
    btc = news["bitcoin"]
    assert btc.tone and btc.count
    assert date(2026, 11, 5) in btc.covered_tone and date(2026, 11, 5) in btc.covered_count
    assert set(btc.tone) <= btc.covered_tone and set(btc.count) <= btc.covered_count


def test_rows_never_use_gdelt_days_after_the_asof_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(B, "FIRST_QUESTION_DAY", date(2026, 10, 1))
    seen: list[tuple[date, str]] = []
    real = S.gdelt_context

    def spy(tone, count, covered, asof):  # type: ignore[no-untyped-def]
        ctx = real(tone, count, covered, asof)
        if ctx:
            days = [d for d, _ in ctx["tone"]] + [d for d, _ in ctx["count"]]
            seen.append((asof.date(), max(days)))
        return ctx

    monkeypatch.setattr(S, "gdelt_context", spy)
    rows = B.build_rows(fixture_crypto(), B.load_news(HISTORY), date(2026, 10, 20))
    assert rows and seen
    for batch, newest in seen:
        assert date.fromisoformat(newest) <= batch - timedelta(days=2)
    assert {r.template for r in rows} <= set(S.TEMPLATES)
    assert all(0 <= r.p_ml <= 1 and 0 < r.base < 1 for r in rows)


def _row(
    day: date, template: str = "up", y: int = 0, vec: tuple[float, ...] | None = None
) -> B.Row:
    v = list(vec) if vec is not None else [float(day.toordinal()), 0.0, 0.0]
    return B.Row(day, "bitcoin", template, y, 0.5, 0.5, v, "")


def test_walk_forward_trains_only_on_outcomes_known_that_morning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = date(2026, 3, 12)
    rows = [_row(first - timedelta(days=100) + timedelta(days=i), y=i % 2) for i in range(200)]
    newest_training_day: list[int] = []
    real_fit = S.fit

    def spy(template, x, y):  # type: ignore[no-untyped-def]
        if len(x):  # the first feature is the batch day's ordinal
            newest_training_day.append(int(max(row[0] for row in x)))
        return real_fit(template, x, y)

    monkeypatch.setattr(S, "fit", spy)
    out = B.walk_forward(rows, first)
    assert out and all(r.day >= first for r, _ in out)
    assert newest_training_day
    for k, newest in enumerate(newest_training_day):
        refit = first + timedelta(days=B.REFIT_EVERY * k)
        assert newest <= (refit - timedelta(days=B.GAP_DAYS)).toordinal()


def test_summarise_marks_small_samples_inconclusive() -> None:
    first = B.FIRST_TEST_DAY
    rows = [
        _row(first + timedelta(days=i), "bigmove", i % 2, (0.1, 0.0, 0.0, 0.0)) for i in range(100)
    ]
    scored = [(r, 0.5) for r in rows]
    s = B.summarise(rows, scored)
    assert any("inconclusive" in n and "bigmove" in n for n in s["notes"])
    assert s["metrics"]["sentiment / bigmove"]["brier"] == pytest.approx(0.25)
    pairs = {(p["b"], p["split"]) for p in s["paired"]}
    assert ("ml", "bigmove") in pairs and ("ml", "up") not in pairs
