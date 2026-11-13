import math
import random

import pytest

from arena.scoring.core import (
    Scored,
    brier,
    brier_skill,
    clip,
    leaderboard,
    log_score,
)


@pytest.mark.parametrize("seed", range(20))
def test_perfect_forecaster_scores_zero_after_clipping_bound(seed: int) -> None:
    rng = random.Random(seed)
    ys = [rng.randint(0, 1) for _ in range(rng.randint(1, 200))]
    # Raw perfect probabilities are clipped to 0.01/0.99, so Brier is exactly 0.0001.
    assert brier([float(y) for y in ys], ys) == pytest.approx(0.01**2)
    # Without clipping effects (already inside the bounds) a perfect score is 0.
    assert brier([0.99 if y else 0.01 for y in ys], ys) == pytest.approx(1e-4)


@pytest.mark.parametrize("seed", range(20))
def test_perfect_is_zero_without_clipping(seed: int) -> None:
    rng = random.Random(seed)
    ys = [rng.randint(0, 1) for _ in range(rng.randint(1, 200))]
    assert brier([float(y) for y in ys], ys, clipped=False) == 0.0


@pytest.mark.parametrize("seed", range(20))
def test_constant_half_is_a_quarter(seed: int) -> None:
    rng = random.Random(seed)
    ys = [rng.randint(0, 1) for _ in range(rng.randint(1, 200))]
    assert brier([0.5] * len(ys), ys) == pytest.approx(0.25)
    assert log_score([0.5] * len(ys), ys) == pytest.approx(math.log(2))


@pytest.mark.parametrize("seed", range(10))
def test_brier_bounds_and_propriety(seed: int) -> None:
    rng = random.Random(seed)
    ys = [rng.randint(0, 1) for _ in range(100)]
    ps = [rng.random() for _ in ys]
    assert 0 <= brier(ps, ys) <= 1
    # Proper: for a true frequency q, the expected score is minimised at p = q.
    q = rng.random()

    def expected(p: float) -> float:
        return q * (clip(p) - 1) ** 2 + (1 - q) * clip(p) ** 2

    best = min((i / 100 for i in range(1, 100)), key=expected)
    assert abs(best - min(max(q, 0.01), 0.99)) <= 0.01


def test_clipping_keeps_log_score_finite() -> None:
    assert log_score([0.0], [1]) == pytest.approx(-math.log(0.01))
    assert clip(-1) == 0.01 and clip(2) == 0.99 and clip(0.3) == 0.3


def test_skill() -> None:
    assert brier_skill(0.2, 0.25) == pytest.approx(0.2)
    assert brier_skill(0.1, 0.0) is None


def test_bad_inputs() -> None:
    with pytest.raises(ValueError):
        brier([], [])
    with pytest.raises(ValueError):
        brier([0.5], [2])


def test_leaderboard_skill_on_common_questions() -> None:
    from datetime import date

    def s(qid: str, fid: str, p: float, y: int) -> Scored:
        return Scored(qid, fid, "1", "power", date(2026, 1, 1), p, y)

    rows = leaderboard(
        [
            s("a", "base_rate", 0.5, 1),
            s("b", "base_rate", 0.5, 0),
            s("a", "ml", 0.9, 1),
            s("b", "ml", 0.1, 0),
            s("c", "ml", 0.9, 0),
        ]
    )
    by = {r.forecaster_id: r for r in rows}
    assert by["ml"].n == 3 and by["ml"].skill_n == 2
    assert by["ml"].skill == pytest.approx(1 - 0.01 / 0.25)
    assert by["base_rate"].skill == pytest.approx(0.0)
