from datetime import UTC, date, datetime, time

import pytest
from attention_fixtures import FixtureSource

from arena.domains.attention import AttentionDomain
from arena.forecasters.ml import MLForecaster
from arena.forecasters.ml_attention import features, train, training_rows
from arena.models import Forecast


@pytest.fixture(scope="module")
def dom():
    return AttentionDomain(FixtureSource())


def test_training_rows_have_labels_from_later_lists(dom) -> None:
    rows = training_rows(dom, date(2026, 11, 1), date(2026, 11, 6))
    assert len(rows.y) > 500 and set(rows.y) == {0, 1}
    assert max(rows.ref) <= date(2026, 11, 6)
    assert len({len(x) for x in rows.x}) == 1


def test_model_forecasts_attention_questions(dom) -> None:
    model = train(dom, date(2026, 10, 15), date(2026, 11, 3), folds=1, fold_days=7, max_iter=30)
    assert model.version.startswith("attention-hgb-r1-2026-11-03")
    b = date(2026, 11, 8)
    asof = datetime.combine(b, time(5, 30), tzinfo=UTC)
    f = MLForecaster({"attention": model})
    for q in dom.generate_questions(b, asof):
        ctx = dom.context(q, asof)
        assert ctx["top_trajectory"][-1]["day"] == q.params["reference_day"]
        out = f.forecast(q, ctx, asof)
        assert isinstance(out, Forecast) and 0 < out.probability < 1


def test_features_require_views_on_reference_day() -> None:
    traj = [
        {"day": f"2026-11-0{d}", "views": 100 * d, "rank": 50, "floor": 10} for d in range(1, 8)
    ]
    assert len(features(traj, 500, "de.wikipedia", date(2026, 11, 10))) == 3 + 6 + 3 + 2 + 7
    traj[-1]["views"] = None
    with pytest.raises(ValueError):
        features(traj, 500, "de.wikipedia", date(2026, 11, 10))
