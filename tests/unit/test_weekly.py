from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest
from power_fixtures import fixture_domain

from arena.clock import FixedClock
from arena.forecasters import registry
from arena.forecasters.ml_power import train
from arena.ledger import Ledger
from arena.ledger.verify import verify
from arena.ops.weekly import summaries, weekly, window

NOW = datetime(2026, 11, 10, 2, tzinfo=UTC)


@dataclass
class Constant:
    """A deliberately bad model: always 0.99."""

    version: str = "power-constant-0.99"

    def probability(self, q, ctx) -> float:
        return 0.99

    def model_hash(self) -> str:
        return self.version


@pytest.fixture(scope="module")
def dom():
    return fixture_domain()


def trainer(dom):
    return lambda cutoff: train(dom, cutoff, folds=1, fold_days=30, max_iter=10)


def test_window() -> None:
    assert window(date(2026, 11, 10)) == (date(2026, 10, 11), date(2026, 11, 7))


def test_first_run_promotes_then_a_worse_candidate_is_kept_out(tmp_path, dom) -> None:
    led = Ledger(tmp_path)
    res = weekly(
        led, FixedClock(NOW), {"power": dom}, {"power": trainer(dom)}, mlruns=tmp_path / "mlruns"
    )
    (d,) = res.decisions
    assert d.promoted and d.n > 100 and d.brier_current is None and "first model" in d.reason
    assert registry.current_version(led, "power") == d.promoted
    later = FixedClock(datetime(2026, 11, 11, 2, tzinfo=UTC))
    res2 = weekly(led, later, {"power": dom}, {"power": lambda c: Constant()})
    (d2,) = res2.decisions
    assert d2.promoted is None and "worse" in d2.reason
    assert d2.brier_candidate > d2.brier_current
    assert registry.current_version(led, "power") == d.promoted
    assert [s["day"] for s in summaries(led)] == ["2026-11-11", "2026-11-10"]
    assert verify(led).ok


def test_dry_run_writes_nothing(tmp_path, dom) -> None:
    led = Ledger(tmp_path)
    res = weekly(led, FixedClock(NOW), {"power": dom}, {"power": trainer(dom)}, dry_run=True)
    assert res.decisions[0].promoted and led.list_files() == []


def test_mlflow_logging_when_installed(tmp_path, dom) -> None:
    pytest.importorskip("mlflow")
    from arena.ops.weekly import Decision, WeeklyResult, log_mlflow

    r = WeeklyResult(
        date(2026, 11, 10),
        [
            Decision(
                "power", date(2026, 10, 11), date(2026, 11, 7), n=5, brier_candidate=0.2, reason="x"
            )
        ],
    )
    assert log_mlflow(r, tmp_path / "mlruns") is not None
    assert (tmp_path / "mlruns" / "mlflow.db").exists()
