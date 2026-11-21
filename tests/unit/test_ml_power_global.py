"""T275: the global LightGBM power model (fixtures only, no network)."""

import io
from datetime import date

import numpy as np
import pytest

pytest.importorskip("lightgbm")

import joblib
from power_fixtures import fixture_domain

from arena.forecasters.ml_power import QUANTILES, STATS, train
from arena.forecasters.ml_power_global import (
    FAMILY,
    StatView,
    fit_global_quantiles,
    train_global,
)

CUT = date(2026, 10, 20)


@pytest.fixture(scope="module")
def dom():
    return fixture_domain()


@pytest.fixture(scope="module")
def model(dom):
    return train_global(dom, CUT, folds=1)


def test_one_fit_serves_every_statistic_and_level() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(200, 4))
    ys = {
        s: rng.normal(loc=100 * (i + 1), scale=10 * (i + 1), size=200) for i, s in enumerate(STATS)
    }
    out = fit_global_quantiles(x, ys, {"n_estimators": 20}, seed=0)
    assert set(out) == set(STATS) and all(len(v) == len(QUANTILES) for v in out.values())
    # the shared model is one LightGBM per level, viewed once per statistic
    assert out[STATS[0]][0].model is out[STATS[1]][0].model
    for i, s in enumerate(STATS):  # predictions come back on each statistic's own scale
        median = out[s][len(QUANTILES) // 2].predict(x[:50])
        assert abs(float(np.mean(median)) - 100 * (i + 1)) < 40 * (i + 1)


def test_the_model_is_a_normal_power_model_with_its_own_family(dom, model) -> None:
    assert model.family == FAMILY and model.version.startswith(f"{FAMILY}-r")
    assert model.version.endswith(CUT.isoformat())
    assert set(model.models) == set(STATS) and isinstance(model.models["mean"][0], StatView)
    from datetime import UTC, datetime

    from arena.forecasters.ml_power import features

    asof = datetime(2026, 10, 21, 5, 30, tzinfo=UTC)
    q0 = dom.generate_questions(date(2026, 10, 21), asof)[0]
    ctx = dom.context(q0, asof)
    qs = model.quantiles("mean", features(ctx["daily"], q0.target_date))
    assert len(qs) == len(QUANTILES) and np.all(np.isfinite(qs))


def test_probabilities_are_valid_on_real_questions(dom, model) -> None:
    from datetime import UTC, datetime

    b = date(2026, 10, 21)
    asof = datetime(2026, 10, 21, 5, 30, tzinfo=UTC)
    qs = dom.generate_questions(b, asof)
    assert qs
    for q in qs:
        p = model.probability(q, dom.context(q, asof))
        assert 0.0 <= p <= 1.0 and np.isfinite(p)


def test_artefact_round_trip_keeps_predictions(dom, model) -> None:
    from datetime import UTC, datetime

    buf = io.BytesIO()
    joblib.dump(model, buf)
    again = joblib.load(io.BytesIO(buf.getvalue()))
    asof = datetime(2026, 10, 21, 5, 30, tzinfo=UTC)
    q = dom.generate_questions(date(2026, 10, 21), asof)[0]
    ctx = dom.context(q, asof)
    assert again.probability(q, ctx) == pytest.approx(model.probability(q, ctx))


def test_default_training_path_is_unchanged_by_the_multi_fitter_hook(dom) -> None:
    base = train(dom, CUT, folds=1, max_iter=20)
    assert base.family != FAMILY and all(isinstance(m, list) for m in base.models.values())
