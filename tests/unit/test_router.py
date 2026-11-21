"""T273: the cascade router decides from peers' forecasts, adds no calls and is versioned."""

import json
from datetime import UTC, datetime

import pytest
from factories import question

from arena.forecasters import router as rt
from arena.models import Forecast, Skip

ASOF = datetime(2026, 11, 24, 7, tzinfo=UTC)
PARAMS = rt.RouterParams(delta=0.2, gamma=0.1, chosen_on="validation days", prereg_sha256="ab" * 32)


def run(peers: dict[str, float]):
    return rt.RouterForecaster(PARAMS).forecast(question(), {"peer_forecasts": peers}, ASOF)


def test_cheap_pair_answers_when_decisive_and_in_agreement() -> None:
    out = run({"ml": 0.80, "llm_local_ft": 0.74, "llm_context": 0.30})
    assert isinstance(out, Forecast)
    assert out.probability == pytest.approx(0.77)
    assert out.meta["escalated"] is False and out.meta["paid_calls_avoided"] == 1


def test_it_escalates_when_unsure_or_disagreeing() -> None:
    unsure = run({"ml": 0.55, "llm_local_ft": 0.60, "llm_context": 0.31})
    assert isinstance(unsure, Forecast) and unsure.probability == 0.31
    assert unsure.meta["escalated"] is True and unsure.meta["paid_calls_avoided"] == 0
    split = run({"ml": 0.90, "llm_local_ft": 0.60, "llm_context": 0.42})
    assert isinstance(split, Forecast) and split.probability == 0.42  # |0.9-0.6| > gamma


def test_a_single_available_cheap_forecast_is_enough_when_decisive() -> None:
    out = run({"ml": 0.12, "llm_context": 0.50})
    assert isinstance(out, Forecast) and out.probability == pytest.approx(0.12)
    assert out.meta["cheap"] == {"ml": 0.12}


def test_no_strong_forecast_means_no_avoided_call_and_possibly_a_skip() -> None:
    out = run({"ml": 0.85, "llm_local_ft": 0.80})  # question outside the LLM sample
    assert isinstance(out, Forecast) and out.meta["paid_calls_avoided"] == 0
    skip = run({"ml": 0.52})
    assert isinstance(skip, Skip) and skip.reason_code == "model_missing"
    assert isinstance(run({}), Skip)


def test_probability_is_clipped() -> None:
    out = run({"ml": 1.0, "llm_local_ft": 1.0})
    assert isinstance(out, Forecast) and out.probability == 0.99


def test_version_carries_the_thresholds_and_the_pin_file_round_trips(tmp_path) -> None:
    v = rt.RouterForecaster(PARAMS).version()
    assert "delta-0.200" in v and "gamma-0.100" in v and v.endswith("ml+llm_local_ft>llm_context")
    other = rt.RouterParams(0.25, 0.1, "x", "cd" * 32)
    assert rt.RouterForecaster(other).version() != v
    assert rt.load_params(tmp_path / "none.json") is None
    p = tmp_path / "p.json"
    p.write_text(json.dumps(PARAMS.__dict__))
    assert rt.load_params(p) == PARAMS


def test_it_is_registered_only_when_the_thresholds_are_frozen(tmp_path, monkeypatch) -> None:
    from factories import B

    from arena.config import Settings
    from arena.ledger import Ledger
    from arena.ops.wiring import build_forecasters

    monkeypatch.setattr(rt, "load_params", lambda path=rt.DEFAULT_PATH: None)
    fs, _ = build_forecasters(Ledger(tmp_path), [], Settings.from_env({}), B, dry_run=True)
    assert "llm_router" not in [f.forecaster_id for f in fs]
    monkeypatch.setattr(rt, "load_params", lambda path=rt.DEFAULT_PATH: PARAMS)
    fs, _ = build_forecasters(Ledger(tmp_path), [], Settings.from_env({}), B, dry_run=True)
    ids = [f.forecaster_id for f in fs]
    assert "llm_router" in ids and getattr(fs[ids.index("llm_router")], "needs_peers", False)
    assert ids.index("llm_router") > ids.index("llm_context")
