"""T277: ONNX export of the LightGBM power families: parity with the original models."""

from datetime import UTC, date, datetime, time

import pytest

pytest.importorskip("lightgbm")
pytest.importorskip("onnxruntime")
pytest.importorskip("onnxmltools")

from power_fixtures import fixture_domain

from arena.forecasters.ml_power_global import train_global
from arena.forecasters.ml_power_lgbm import train_lgbm
from arena.forecasters.onnx_power import PARITY_TOLERANCE, OnnxPowerModel, export_model

CUT = date(2026, 10, 20)


@pytest.fixture(scope="module")
def dom():
    return fixture_domain()


def _rows(dom):
    b = date(2026, 10, 21)
    asof = datetime.combine(b, time(5, 30), tzinfo=UTC)
    return [(q, dom.context(q, asof)) for q in dom.generate_questions(b, asof)]


@pytest.mark.parametrize("which", ["global", "per-stat"])
def test_probabilities_and_quantiles_match_the_original(dom, tmp_path, which) -> None:
    model = train_global(dom, CUT, folds=1) if which == "global" else train_lgbm(dom, CUT, folds=1)
    manifest = export_model(model, tmp_path)
    onx = OnnxPowerModel(tmp_path)
    assert onx.version == model.version == manifest["version"]
    checked = 0
    for q, ctx in _rows(dom):
        want = model.probability(q, ctx)
        thr = float(q.params["reference_mean"]) if q.template == "up_vs_today" else q.threshold
        got = onx.probability(str(q.params["stat"]), ctx["daily"], q.target_date, thr, q.comparator)
        assert abs(got["probability"] - want) < PARITY_TOLERANCE
        checked += 1
    assert checked >= 4


def test_a_changed_file_is_refused(dom, tmp_path) -> None:
    export_model(train_global(dom, CUT, folds=1), tmp_path)
    f = next(tmp_path.glob("q*.onnx"))
    f.write_bytes(f.read_bytes() + b"\0")
    with pytest.raises(ValueError, match="hash"):
        OnnxPowerModel(tmp_path)


def test_predict_power_endpoint(dom, tmp_path, monkeypatch) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from arena.api.app import create_app
    from arena.ledger import Ledger

    model = train_global(dom, CUT, folds=1)
    export_model(model, tmp_path / "onnx")
    q, ctx = _rows(dom)[0]
    body = {
        "stat": q.params["stat"],
        "target_date": q.target_date.isoformat(),
        "daily": ctx["daily"],
        "threshold": q.threshold if q.threshold is not None else float(q.params["reference_mean"]),
        "comparator": q.comparator,
    }
    monkeypatch.delenv("ARENA_ONNX_DIR", raising=False)
    off = TestClient(create_app(Ledger(tmp_path / "led")))
    assert off.post("/predict/power", json=body).status_code == 503
    monkeypatch.setenv("ARENA_ONNX_DIR", str(tmp_path / "onnx"))
    on = TestClient(create_app(Ledger(tmp_path / "led")))
    r = on.post("/predict/power", json=body)
    assert r.status_code == 200 and r.json()["version"] == model.version
    assert abs(r.json()["probability"] - model.probability(q, ctx)) < PARITY_TOLERANCE
    assert on.post("/predict/power", json={**body, "stat": "bogus"}).status_code == 422
