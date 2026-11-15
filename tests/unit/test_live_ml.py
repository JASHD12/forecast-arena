"""The production factory must expose ML successes and failures, never omit the competitor."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from factories import question

from arena.clock import FixedClock
from arena.config import Settings
from arena.forecasters import registry
from arena.forecasters.ml import MLForecaster
from arena.forecasters.ml_crypto import CryptoModel
from arena.forecasters.ml_markets import MarketsModel
from arena.forecasters.ml_weather import WeatherRules
from arena.ledger import Ledger
from arena.models import Forecast, Skip
from arena.ops.wiring import build_forecasters, live_ml

AT = datetime(2026, 11, 12, 2, tzinfo=UTC)
NOW = AT.replace(hour=6)


@dataclass
class ConstantModel:
    version: str = "test-r1"
    p: float = 0.3

    def probability(self, q, ctx) -> float:
        return self.p

    def model_hash(self) -> str:
        return self.version


def domains(*names):
    return [SimpleNamespace(name=n, replayable=False) for n in names]


def publish(ledger, name="power", model=None, at=AT):
    model = model or ConstantModel()
    info = registry.save_model(ledger, name, model, created_at=at)
    registry.promote(ledger, name, model.version, at=at, reason="test")
    return info


def test_factory_keeps_ml_when_registry_empty_and_shares_it_with_agents(tmp_path) -> None:
    ledger = Ledger(tmp_path)
    fs, _ = build_forecasters(
        ledger, domains("power"), Settings.from_env({}), NOW.date(), clock=FixedClock(NOW)
    )
    by = {f.forecaster_id: f for f in fs}
    assert len(by) == len(fs) and isinstance(by["ml"], MLForecaster)
    out = by["ml"].forecast(question(), {}, NOW)
    assert isinstance(out, Skip) and out.reason_code == "model_missing"
    assert by["agent"].peers["ml"] is by["ml"]
    bare, _ = build_forecasters(ledger, [], clock=FixedClock(NOW))
    assert [f.forecaster_id for f in bare] == ["base_rate", "persistence", "ml"]


def test_only_loaded_domains_get_rules(tmp_path) -> None:
    f = live_ml(Ledger(tmp_path), domains("weather", "markets"), NOW)
    assert isinstance(f.models["weather"], WeatherRules)
    assert isinstance(f.models["markets"], MarketsModel)
    assert "crypto" not in f.models
    crypto = live_ml(Ledger(tmp_path), domains("crypto"), NOW)
    assert isinstance(crypto.models["crypto"], CryptoModel)


def test_promoted_model_is_loaded_once_with_verified_artifact_identity(tmp_path) -> None:
    ledger = Ledger(tmp_path)
    first = publish(ledger)
    f = live_ml(ledger, domains("power"), NOW)
    out = f.forecast(question(), {}, NOW)
    assert isinstance(out, Forecast)
    assert out.forecaster_version == first.version and out.probability == 0.3
    assert out.meta["artifact_sha256"] == first.sha256
    later = NOW + timedelta(days=1)
    publish(ledger, model=ConstantModel("test-r2", 0.7), at=later)
    # The next promotion is invisible to an earlier as-of and to the already-loaded run.
    assert registry.current_version(ledger, "power", asof=NOW) == first.version
    assert f.forecast(question(), {}, later).probability == 0.3
    newer = live_ml(ledger, domains("power"), later)
    assert newer.forecast(question(), {}, later).probability == 0.7


@pytest.mark.parametrize("failure", ["missing", "corrupt", "runtime", "identity", "future"])
def test_bad_power_artifact_does_not_disable_other_models(tmp_path, monkeypatch, failure) -> None:
    ledger = Ledger(tmp_path)
    info = publish(ledger)
    publish(ledger, name="attention")
    path = ledger.abspath(f"models/power/{info.version}/{registry.ARTEFACT}")
    if failure == "missing":
        path.unlink()
    elif failure == "corrupt":
        path.write_bytes(b"corrupt artifact")
    elif failure == "runtime":
        real_load = registry.load

        def load(led, name, version):
            if name == "power":
                raise ModuleNotFoundError("missing inference runtime")
            return real_load(led, name, version)

        monkeypatch.setattr(registry, "load", load)
    else:
        path = ledger.abspath(f"models/power/{info.version}/metadata.json")
        meta = json.loads(path.read_bytes())
        if failure == "identity":
            meta["version"] = "another-version"
        else:
            meta["created_at"] = (NOW + timedelta(days=1)).isoformat()
        path.write_text(json.dumps(meta))
    fs, _ = build_forecasters(
        ledger, domains("power", "attention", "weather"), clock=FixedClock(NOW)
    )
    f = next(x for x in fs if isinstance(x, MLForecaster))
    bad = f.forecast(question(), {}, NOW)
    assert isinstance(bad, Skip) and bad.reason_code == "error"
    assert bad.forecaster_version == info.version and "model load failed" in bad.detail
    good = f.forecast(question().model_copy(update={"domain": "attention"}), {}, NOW)
    assert isinstance(good, Forecast) and good.probability == 0.3
    assert isinstance(f.models["weather"], WeatherRules)
    assert {x.forecaster_id for x in fs} == {"base_rate", "persistence", "ml"}
