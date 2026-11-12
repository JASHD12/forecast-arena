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
