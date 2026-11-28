"""The news-lag note (T402): current, and consistent with the as-of rule it explains."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from arena.backtest.sentiment import News
from arena.lab import sentiment_lag as L

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import sentiment_lag_study as study  # noqa: E402


def test_card_is_current() -> None:
    assert study.OUT.read_text(encoding="utf-8") == study.render()


def test_the_offsets_are_the_ones_the_as_of_rule_uses() -> None:
    assert L.OFFSETS[0] == 1 and L.OFFSETS[-1] == -3  # after the move ... what a question can see


def test_a_signal_that_follows_the_move_is_found_at_k_plus_one_only() -> None:
    """Synthetic: the volume surprise on day D+1 equals the size of the move of day D."""
    start = date(2026, 1, 1)
    days = [start + timedelta(days=i) for i in range(120)]
    rng_moves = [float(m) for m in np.random.default_rng(0).uniform(0.005, 0.05, len(days))]
    price = {days[0]: 100.0}
    for i, d in enumerate(days[1:], 1):
        price[d] = price[days[i - 1]] * (1 + rng_moves[i - 1] * (1 if i % 2 else -1))
    count = {}
    for i, d in enumerate(days):  # day D+1's count carries the move of day D
        count[d] = int(100 * (1 + 20 * (rng_moves[i - 1] if i else 0.0)))
    news = News(count=count, covered_count=set(days), tone={d: -0.5 for d in days})
    rows = {int(r["offset"]): r for r in L.lag_table({"bitcoin": price}, {"bitcoin": news})}
    assert rows[1]["corr_volume_abs_move"] > 0.8
    assert abs(rows[-3]["corr_volume_abs_move"] or 0.0) < 0.3
