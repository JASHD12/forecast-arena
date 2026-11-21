"""T260: occlusion explanations of the power model's probabilities."""

from datetime import UTC, date, datetime, time

import numpy as np
import pytest
from power_fixtures import fixture_domain

from arena.forecasters.ml_power import STATS, features, train
from arena.lab.explanations import background, explain, groups, probability_from


@pytest.fixture(scope="module")
def setup():
    dom = fixture_domain()
    model = train(dom, date(2026, 10, 20), folds=1, fold_days=40, max_iter=15)
    b = date(2026, 10, 21)
    asof = datetime.combine(b, time(5, 30), tzinfo=UTC)
    q = dom.generate_questions(b, asof)[0]
    ctx = dom.context(q, asof)
    return dom, model, q, ctx


def test_groups_cover_every_feature_once() -> None:
    cols = sorted(i for _, ix in groups() for i in ix)
    assert cols == list(range(12 + 5 * len(STATS)))


def test_explanation_reproduces_the_models_probability_and_lists_three_effects(setup) -> None:
    _, model, q, ctx = setup
    x = features(ctx["daily"], q.target_date)
    typical = background([features(ctx["daily"][: k + 1], q.target_date) for k in range(14, 21)])
    thr = q.threshold if q.threshold is not None else float(q.params["reference_mean"])
    out = explain(model, str(q.params["stat"]), x, thr, q.comparator, typical)
    assert out["probability"] == pytest.approx(model.probability(q, ctx))
    assert len(out["top"]) == 3
    mags = [abs(t["effect_points"]) for t in out["top"]]
    assert mags == sorted(mags, reverse=True)


def test_replacing_with_the_input_itself_changes_nothing(setup) -> None:
    _, model, q, ctx = setup
    x = np.asarray(features(ctx["daily"], q.target_date))
    thr = q.threshold if q.threshold is not None else float(q.params["reference_mean"])
    out = explain(model, str(q.params["stat"]), list(x), thr, q.comparator, x)
    assert all(t["effect_points"] == 0 for t in out["top"])
    assert (
        probability_from(model, str(q.params["stat"]), list(x), thr, q.comparator)
        == out["probability"]
    )
