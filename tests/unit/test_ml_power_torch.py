from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

pytest.importorskip("torch")

from power_fixtures import fixture_domain

from arena.forecasters.ml_power import QUANTILES
from arena.forecasters.ml_power_torch import FAMILY, fit_quantiles_torch, train_torch

CUT = date(2026, 10, 20)


def _data(n: int = 300) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(n, 4))
    y = 50 + 10 * x[:, 0] + rng.normal(scale=5, size=n)
    return x, y


def test_deterministic_sorted_and_learns_signal() -> None:
    x, y = _data()
    a = fit_quantiles_torch(x, y, epochs=150)
    b = fit_quantiles_torch(x, y, epochs=150)
    assert len(a) == len(QUANTILES)
    pa = np.array([h.predict(x[:30]) for h in a])
    pb = np.array([h.predict(x[:30]) for h in b])
    assert np.array_equal(pa, pb)  # same seed, same model
    assert np.all(np.diff(pa, axis=0) >= 0)  # quantiles never cross
    median = a[QUANTILES.index(0.5)].predict(x)
    assert np.corrcoef(median, 10 * x[:, 0])[0, 1] > 0.8  # picks up the real signal
    inside = np.mean((pa[2] <= y[:30]) & (y[:30] <= pa[-3]))  # 10%..90% band
    assert inside > 0.5


def test_challenger_model_answers_questions() -> None:
    dom = fixture_domain()
    model = train_torch(dom, CUT, folds=1, epochs=100)
    assert model.version == f"{FAMILY}-r1-{CUT.isoformat()}"
    b = CUT + timedelta(days=1)
    asof = datetime(b.year, b.month, b.day, 5, 30, tzinfo=UTC)
    qs = dom.generate_questions(b, asof)
    assert qs
    for q in qs:
        assert 0.0 < model.probability(q, dom.context(q, asof)) < 1.0
