from datetime import UTC, date, datetime, time

import pytest
from factories import question
from power_fixtures import fixture_domain

from arena.forecasters.ml import MLForecaster
from arena.forecasters.ml_power import train
from arena.forecasters.registry import (
    RegistryError,
    current_version,
    load,
    load_current,
    promote,
    save_model,
    versions,
)
from arena.ledger import Ledger, LedgerError
from arena.models import Forecast, Skip

AT = datetime(2026, 11, 15, 2, tzinfo=UTC)


@pytest.fixture(scope="module")
def model():
    return train(fixture_domain(), date(2026, 8, 31), folds=1, fold_days=40, max_iter=10)


def test_save_load_promote_and_version_reporting(tmp_path, model) -> None:
    led = Ledger(tmp_path)
    info = save_model(led, "power", model, created_at=AT, card="# card")
    assert versions(led, "power") == [model.version] and current_version(led, "power") is None
    assert load_current(led, ["power"]) == {}
    promote(led, "power", model.version, at=AT, reason="first model")
    loaded = load_current(led, ["power", "weather"])
    assert set(loaded) == {"power"} and loaded["power"].version == model.version
    assert info.meta["artefact_bytes"] < 2_000_000
    f = MLForecaster(loaded)
    assert f.version() == model.version
    b = date(2026, 10, 20)
    asof = datetime.combine(b, time(5, 30), tzinfo=UTC)
    dom = fixture_domain()
    q = dom.generate_questions(b, asof)[0]
    out = f.forecast(q, dom.context(q, asof), asof)
    assert isinstance(out, Forecast) and out.forecaster_version == model.version
    with pytest.raises(LedgerError):
        save_model(led, "power", model, created_at=AT)  # versions are never overwritten


def test_missing_model_is_a_skip(tmp_path) -> None:
    models = load_current(Ledger(tmp_path), ["power"])
    out = MLForecaster(models).forecast(question(), {}, AT)
    assert isinstance(out, Skip) and out.reason_code == "model_missing"
    with pytest.raises(RegistryError):
        promote(Ledger(tmp_path), "power", "nope", at=AT, reason="x")


def test_tampered_artefact_refused(tmp_path, model) -> None:
    led = Ledger(tmp_path)
    save_model(led, "power", model, created_at=AT)
    path = led.abspath(f"models/power/{model.version}/model.joblib.xz")
    path.write_bytes(path.read_bytes()[:-10] + b"0" * 10)
    with pytest.raises(RegistryError, match="hash"):
        load(led, "power", model.version)


def test_ledger_with_models_still_verifies(tmp_path, model) -> None:
    from arena.ledger.verify import verify

    led = Ledger(tmp_path)
    save_model(led, "power", model, created_at=AT)
    promote(led, "power", model.version, at=AT, reason="x")
    rep = verify(led)
    assert rep.ok, rep.summary()
