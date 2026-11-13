from datetime import UTC, date, datetime, timedelta

import numpy as np
import pytest

pytest.importorskip("lightgbm")
pytest.importorskip("optuna")

from power_fixtures import fixture_domain

from arena.forecasters.ml_power import QUANTILES
from arena.forecasters.ml_power_lgbm import (
    DEFAULT_PARAMS,
    FAMILY,
    fit_quantiles_lgbm,
    pinball_loss,
    train_lgbm,
    tune_lgbm,
)

CUT = date(2026, 10, 20)


@pytest.fixture(scope="module")
def dom():
    return fixture_domain()


@pytest.fixture(scope="module")
def model(dom):
    return train_lgbm(dom, CUT, n_trials=3, folds=1)


def test_pinball_loss() -> None:
    y = np.array([10.0, 10.0])
    assert pinball_loss(y, np.array([8.0, 8.0]), 0.9) == pytest.approx(1.8)
    assert pinball_loss(y, np.array([12.0, 12.0]), 0.9) == pytest.approx(0.2)


def test_one_regressor_per_quantile_and_roughly_ordered() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(400, 3))
    y = 2 * x[:, 0] + rng.normal(size=400)
    ms = fit_quantiles_lgbm(x, y, {"n_estimators": 60})
    assert len(ms) == len(QUANTILES)
    preds = np.array([m.predict(x[:50]) for m in ms])
    assert np.mean(preds[0] < preds[-1]) > 0.95  # 2% quantile below 98% quantile


def test_tuning_is_deterministic_and_falls_back_when_short() -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(size=(300, 3))
    y = x[:, 0] + rng.normal(size=300)
    t = [date(2026, 1, 1) + timedelta(days=i) for i in range(300)]
    a = tune_lgbm(x, y, t, n_trials=3, folds=1)
    b = tune_lgbm(x, y, t, n_trials=3, folds=1)
    assert a == b and set(a) == set(DEFAULT_PARAMS)
    assert tune_lgbm(x[:20], y[:20], t[:20], n_trials=3) == DEFAULT_PARAMS


def test_challenger_model_answers_questions(dom, model) -> None:
    assert model.version == f"{FAMILY}-r1-{CUT.isoformat()}"
    assert set(model.params) == set(DEFAULT_PARAMS)
    b = CUT + timedelta(days=1)
    asof = datetime(b.year, b.month, b.day, 5, 30, tzinfo=UTC)
    qs = dom.generate_questions(b, asof)
    assert qs
    for q in qs:
        assert 0.0 < model.probability(q, dom.context(q, asof)) < 1.0


def test_shap_only_for_the_lightgbm_family(dom, model) -> None:
    pytest.importorskip("shap")
    from arena.forecasters.ml_power import train
    from arena.ops.drift import FEATURE_NAMES
    from arena.ops.explain import TOP, power_shap

    first, last = CUT + timedelta(days=1), CUT + timedelta(days=12)
    rows = power_shap(dom, model, first, last)
    assert 0 < len(rows) <= TOP and {r["feature"] for r in rows} <= set(FEATURE_NAMES)
    vals = [r["mean_abs_shap"] for r in rows]
    assert vals == sorted(vals, reverse=True)
    hgb = train(dom, CUT, folds=1, max_iter=10)
    assert power_shap(dom, hgb, first, last) == []
