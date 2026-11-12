import random

import pytest

from arena.scoring.core import brier
from arena.scoring.stats import (
    calibration_bins,
    day_block_bootstrap,
    expected_calibration_error,
    murphy,
    paired_brier_difference,
)


def synthetic(seed: int, n: int = 2000, calibrated: bool = True):
    rng = random.Random(seed)
    levels = [0.15, 0.35, 0.55, 0.75, 0.95]
    p = [rng.choice(levels) for _ in range(n)]
    y = [int(rng.random() < (q if calibrated else 0.5)) for q in p]
    return p, y


def test_bins_merge_sparse_and_cover_everything() -> None:
    p = [0.05] * 50 + [0.15] * 3 + [0.55] * 40 + [0.95] * 2
    y = [0] * 50 + [1] * 3 + [1] * 20 + [0] * 20 + [1, 1]
    bs = calibration_bins(p, y, min_count=10)
    assert sum(b.n for b in bs) == len(p) and all(b.n >= 10 for b in bs)
    assert bs[0].low == 0.0 and bs[-1].high == 1.0


def test_ece_small_for_calibrated_large_for_uncalibrated() -> None:
    p, y = synthetic(1)
    assert expected_calibration_error(p, y) < 0.04
    p, y = synthetic(1, calibrated=False)
    assert expected_calibration_error(p, y) > 0.15


def test_murphy_identity_is_exact_for_binned_forecasts() -> None:
    for seed in range(5):
        p, y = synthetic(seed)
        m = murphy(p, y)
        assert m.brier == pytest.approx(brier(p, y), abs=1e-12)
        assert m.resolution > 0 and 0 < m.uncertainty <= 0.25


def test_constant_base_rate_forecaster_has_no_resolution() -> None:
    rng = random.Random(3)
    y = [int(rng.random() < 0.3) for _ in range(1000)]
    m = murphy([sum(y) / len(y)] * len(y), y)
    assert m.resolution == pytest.approx(0) and m.reliability == pytest.approx(0)


def test_bootstrap_is_seed_stable_and_covers_truth() -> None:
    rng = random.Random(7)
    days = [d for d in range(60) for _ in range(20)]
    vals = [rng.gauss(0.2, 0.1) for _ in days]
    a = day_block_bootstrap(days, vals)
    b = day_block_bootstrap(days, vals)
    assert a == b and a.low < 0.2 < a.high and a.days == 60
    diff = paired_brier_difference(days, [0.9] * len(days), [0.5] * len(days), [1] * len(days))
    assert diff.estimate == pytest.approx(0.01 - 0.25) and diff.excludes_zero


def test_diebold_mariano_known_cases() -> None:
    import math
    from datetime import date, timedelta

    from arena.scoring.stats import diebold_mariano

    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(40)]
    rng = __import__("numpy").random.default_rng(0)
    noise = rng.normal(0, 0.01, 40)
    better = diebold_mariano(days, [0.1 + e for e in noise], [0.2 + e for e in noise[::-1]])
    assert better is not None and better.statistic < -5 and better.p_value < 1e-6
    assert better.days == 40 and better.lags == int(40 ** (1 / 3))
    same = diebold_mariano(days, list(0.2 + noise), list(0.2 + noise[::-1]))
    assert same is not None and same.p_value > 0.05
    # Same-day forecasts are averaged first: 2 per day still gives 40 daily points.
    dup = diebold_mariano(days + days, [0.1] * 40 + [0.3] * 40, [0.2] * 80)
    assert dup is None  # mean difference 0 every day -> zero variance
    assert diebold_mariano(days[:2], [0.1, 0.2], [0.2, 0.1]) is None
    # Hand check of the HLN-corrected statistic without lags (T = 3).
    r = diebold_mariano(days[:3], [0.3, 0.1, 0.2], [0.1, 0.1, 0.1])
    d = [0.2, 0.0, 0.1]
    m = sum(d) / 3
    var = (
        sum((x - m) ** 2 for x in d) / 3
        + 2 * 0.5 * ((d[1] - m) * (d[0] - m) + (d[2] - m) * (d[1] - m)) / 3
    )
    expected = m / math.sqrt(var / 3) * math.sqrt((3 - 1) / 3)
    assert r is not None and abs(r.statistic - expected) < 1e-9
