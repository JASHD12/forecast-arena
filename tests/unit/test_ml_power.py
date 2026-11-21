from datetime import UTC, date, datetime, time

import pytest
from factories import question
from power_fixtures import fixture_domain

from arena.forecasters.ml import MLForecaster
from arena.forecasters.ml_power import QUANTILES, cdf_at, features, train
from arena.models import Forecast, Skip


@pytest.fixture(scope="module")
def trained():
    dom = fixture_domain()
    model = train(dom, date(2026, 8, 31), folds=1, fold_days=40, max_iter=15)
    return dom, model


def test_cdf_monotone_and_bounded() -> None:
    qv = [float(i) for i in range(len(QUANTILES))]
    vals = [cdf_at(qv, t) for t in (-5, 0, 3.5, 6, 100)]
    assert vals == sorted(vals) and 0 < vals[0] < vals[-1] < 1
    assert cdf_at(list(reversed(qv)), 6) == cdf_at(qv, 6)  # crossing quantiles are sorted


def test_model_answers_power_questions_with_probabilities(trained) -> None:
    dom, model = trained
    assert model.version.startswith("power-gbq-r1-2026-08-31") and model.n_train > 200
    b = date(2026, 10, 20)
    asof = datetime.combine(b, time(5, 30), tzinfo=UTC)
    f = MLForecaster({"power": model})
    for q in dom.generate_questions(b, asof):
        out = f.forecast(q, dom.context(q, asof), asof)
        assert isinstance(out, Forecast) and 0 <= out.probability <= 1
        assert out.forecaster_version == model.version


def test_higher_threshold_means_lower_probability(trained) -> None:
    dom, model = trained
    b = date(2026, 10, 20)
    asof = datetime.combine(b, time(5, 30), tzinfo=UTC)
    q = next(q for q in dom.generate_questions(b, asof) if q.template == "mean_gt")
    ctx = dom.context(q, asof)
    ps = [
        model.raw_probability(q.model_copy(update={"threshold": t}), ctx)
        for t in (0, 50, 100, 200, 400)
    ]
    assert ps == sorted(ps, reverse=True)


def test_missing_model_is_a_skip_not_a_number() -> None:
    q = question()
    out = MLForecaster({}).forecast(q, {}, q.lock_time.replace(hour=6))
    assert isinstance(out, Skip) and out.reason_code == "model_missing"


def test_features_use_only_context_rows() -> None:
    rows = [
        {"day": f"2026-10-{d:02d}", "mean": d, "max": d, "min": d, "spread": 0, "evening": d}
        for d in range(1, 29)
    ]
    x = features(rows, date(2026, 10, 29))
    assert len(x) == 12 + 5 * 5 and x[12] == 28.0


def test_conformal_interval_is_meta_only_and_leaves_the_probability_alone(trained) -> None:
    """T276b: with a CQR margin the forecast meta carries an ordered 80% band."""
    dom, model = trained
    b = date(2026, 10, 20)
    asof = datetime.combine(b, time(5, 30), tzinfo=UTC)
    q = next(q for q in dom.generate_questions(b, asof) if q.params.get("stat") == "mean")
    ctx = dom.context(q, asof)
    plain = MLForecaster({"power": model}).forecast(q, ctx, asof)
    wide = MLForecaster({"power": model}, conformal={"power": {"mean": 7.5}}).forecast(q, ctx, asof)
    assert isinstance(plain, Forecast) and isinstance(wide, Forecast)
    assert "interval80" not in plain.meta  # no margin yet: nothing shown
    assert (
        wide.probability == plain.probability
        and wide.forecaster_version == plain.forecaster_version
    )
    iv = wide.meta["interval80"]
    assert iv["stat"] == "mean" and iv["margin"] == 7.5 and iv["lo"] < iv["hi"]
    narrow = MLForecaster({"power": model}, conformal={"power": {"mean": 0.0}}).forecast(
        q, ctx, asof
    )
    assert isinstance(narrow, Forecast)
    assert wide.meta["interval80"]["lo"] == pytest.approx(
        narrow.meta["interval80"]["lo"] - 7.5, abs=0.02
    )
