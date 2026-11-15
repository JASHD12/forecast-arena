"""Each promotable runtime survives publication and a fresh morning process.

The dedicated CI job installs only base plus inference requirements. No tuning, tracking,
RAG, graph or local-LLM extras may accidentally make model deserialization work.
"""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import pytest
from power_fixtures import fixture_domain

from arena.clock import FixedClock
from arena.forecasters.ml_power import train
from arena.ledger import Ledger
from arena.ops.weekly import weekly

NOW = datetime(2026, 11, 12, 2, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[2]

# Imports blocked in the child are deliberately absent from the inference-only CI job.
CHILD = r"""
import importlib.abc
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

class TrainingOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        training_only = {"optuna", "shap", "mlflow", "evidently", "langgraph", "fastembed"}
        if fullname.split(".")[0] in training_only:
            raise ImportError("training-only dependency requested: " + fullname)
sys.meta_path.insert(0, TrainingOnly())
from power_fixtures import fixture_domain
from arena.clock import FixedClock
from arena.ledger import Ledger
from arena.ledger.verify import verify
from arena.models import Forecast, Skip
from arena.ops.jobs import morning
from arena.ops.wiring import build_forecasters

led = Ledger(Path(sys.argv[1]))
clock = FixedClock(datetime(2026, 11, 12, 6, tzinfo=UTC))
dom = fixture_domain()
forecasters, _ = build_forecasters(led, [dom], clock=clock)
assert [f.forecaster_id for f in forecasters] == ["base_rate", "persistence", "ml"]
result = morning(led, clock.now().date(), clock, [dom], forecasters)
assert result.written.get("batch_seal") == 1
records = [r for _, r in led.iter_family("forecasts")]
ml = [r for r in records if r.forecaster_id == "ml"]
assert ml and all(isinstance(r, Forecast) for r in ml), ml
assert all(0 <= r.probability <= 1 for r in ml)
assert all(r.forecaster_version == sys.argv[2] and r.meta.get("artifact_sha256") for r in ml)
assert not any(isinstance(r, Skip) for r in records)
assert all(r.created_at.hour == 6 for r in ml)
assert verify(led).ok
before = {p: led.read_bytes(p) for p in led.list_files() if not p.startswith("runs/")}
retry = morning(led, clock.now().date(), clock, [dom], forecasters)
assert not retry.written
assert before == {p: led.read_bytes(p) for p in before}
print(json.dumps({"ml_forecasts": len(ml), "version": ml[0].forecaster_version}))
"""


@pytest.mark.parametrize("family", ["hgb", "lgbm", "torch"])
def test_weekly_registry_to_fresh_production_morning(tmp_path, family) -> None:
    dom = fixture_domain()
    kwargs = {"folds": 1, "fold_days": 20, "max_iter": 2}
    if family == "lgbm":
        pytest.importorskip("lightgbm")
        from arena.forecasters.ml_power_lgbm import FAMILY, fit_quantiles_lgbm

        kwargs.update(family=FAMILY, fitter=partial(fit_quantiles_lgbm, params={"n_estimators": 2}))
    elif family == "torch":
        pytest.importorskip("torch")
        from arena.forecasters.ml_power_torch import FAMILY, fit_quantiles_torch

        kwargs.update(family=FAMILY, fitter=partial(fit_quantiles_torch, epochs=2))
    led = Ledger(tmp_path / "ledger")
    result = weekly(
        led,
        FixedClock(NOW),
        {"power": dom},
        {"power": lambda cutoff: train(dom, cutoff, **kwargs)},
        drift=False,
    )
    assert result.ok and result.decisions[0].promoted
    assert result.decisions[0].n > 0
    version = result.decisions[0].promoted
    # Both src and fixtures are explicit, so a globally installed package cannot hide an error.
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT / "tests/unit")]),
    }
    child = subprocess.run(
        [sys.executable, "-c", CHILD, str(led.root), version],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    payload = json.loads(child.stdout)
    assert payload["ml_forecasts"] >= 5 and payload["version"] == version
