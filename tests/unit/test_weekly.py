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


def test_drift_report_from_fixture_data(tmp_path, dom) -> None:
    pytest.importorskip("evidently")
    led = Ledger(tmp_path / "l")
    res = weekly(
        led, FixedClock(NOW), {"power": dom}, {"power": trainer(dom)}, mlruns=tmp_path / "mlruns"
    )
    assert res.drift and any("Drift" in m["metric"] for m in res.drift)
    assert (tmp_path / "mlruns" / "drift-2026-11-10.html").exists()
    (summary,) = summaries(led)
    assert summary["drift"] == res.drift


def test_permutation_importance_in_summary(tmp_path, dom) -> None:
    from arena.ops.drift import FEATURE_NAMES
    from arena.ops.explain import TOP, power_importance

    led = Ledger(tmp_path / "l")
    res = weekly(led, FixedClock(NOW), {"power": dom}, {"power": trainer(dom)}, drift=True)
    assert 0 < len(res.importance) <= TOP
    feats = [r["feature"] for r in res.importance]
    assert set(feats) <= set(FEATURE_NAMES)
    vals = [r["mae_increase"] for r in res.importance]
    assert vals == sorted(vals, reverse=True)
    (summary,) = summaries(led)
    assert summary["importance"]["power"] == res.importance
    first, last = window(NOW.date())
    model = registry.load_current(led, ["power"])["power"]
    assert power_importance(dom, model, first, last) == res.importance  # deterministic
    assert power_importance(dom, Constant(), first, last) == []


def test_pinball_and_quantile_diagnostics(tmp_path, dom) -> None:
    from arena.ops.explain import pinball, power_quantile_diagnostics

    assert pinball(10.0, 8.0, 0.9) == pytest.approx(1.8)
    assert pinball(10.0, 12.0, 0.9) == pytest.approx(0.2)
    assert pinball(10.0, 10.0, 0.5) == 0.0
    led = Ledger(tmp_path / "l")
    res = weekly(led, FixedClock(NOW), {"power": dom}, {"power": trainer(dom)})
    assert {d["stat"] for d in res.quantiles} == {"mean", "max", "min", "spread", "evening"}
    for d in res.quantiles:
        assert d["n"] > 0 and d["pinball"] >= 0
        assert 0 <= d["coverage80"] <= d["coverage90"] <= 1
    (summary,) = summaries(led)
    assert summary["quantile_diagnostics"]["power"] == res.quantiles
    first, last = window(NOW.date())
    assert power_quantile_diagnostics(dom, Constant(), first, last) == []


def test_multi_candidate_promotes_best_family_and_lists_all(tmp_path, dom) -> None:
    def boom(cutoff):
        raise RuntimeError("no data")

    led = Ledger(tmp_path / "l")
    fams = {"hgb": trainer(dom), "constant": lambda c: Constant(), "broken": boom}
    res = weekly(led, FixedClock(NOW), {"power": dom}, {"power": fams}, drift=False)
    (d,) = res.decisions
    assert d.best_family == "hgb" and d.promoted and d.promoted.startswith("power-")
    by = {c["family"]: c for c in d.candidates}
    assert set(by) == {"hgb", "constant", "broken"}
    assert by["broken"]["error"].startswith("training failed: RuntimeError")
    assert by["hgb"]["brier"] < by["constant"]["brier"]
    assert by["hgb"]["n"] == by["constant"]["n"] == d.n  # same questions for every model
    (summary,) = summaries(led)
    assert {c["family"] for c in summary["decisions"][0]["candidates"]} == set(by)
    assert any("power/constant" in line for line in res.lines())


def test_worse_challenger_family_never_replaces_the_champion(tmp_path, dom) -> None:
    led = Ledger(tmp_path / "l")
    weekly(led, FixedClock(NOW), {"power": dom}, {"power": trainer(dom)}, drift=False)
    champion = registry.load_current(led, ["power"])["power"].version
    later = FixedClock(datetime(2026, 11, 17, 2, tzinfo=UTC))
    res = weekly(led, later, {"power": dom}, {"power": {"constant": lambda c: Constant()}},
                 drift=False)  # fmt: skip
    (d,) = res.decisions
    assert d.best_family == "constant" and d.promoted is None
    assert "worse than current" in d.reason
    assert registry.load_current(led, ["power"])["power"].version == champion


def test_conformal_margin_restores_coverage_on_synthetic_data() -> None:
    import numpy as np

    from arena.ops.explain import cqr_margin

    rng = np.random.default_rng(0)
    y_cal, y_new = rng.normal(size=2000), rng.normal(size=20000)
    lo, hi = -0.5, 0.5  # a far too narrow "80%" band (true coverage about 38%)
    m = cqr_margin(np.full(2000, lo), np.full(2000, hi), y_cal, 0.80)
    raw = np.mean((lo <= y_new) & (y_new <= hi))
    adj = np.mean((lo - m <= y_new) & (y_new <= hi + m))
    assert raw < 0.5 and 0.79 <= adj <= 0.83
    wide = cqr_margin(np.full(2000, -5.0), np.full(2000, 5.0), y_cal, 0.80)
    assert wide < 0  # a too wide band is narrowed


def test_conformal_in_weekly_summary(tmp_path, dom) -> None:
    led = Ledger(tmp_path / "l")
    res = weekly(led, FixedClock(NOW), {"power": dom}, {"power": trainer(dom)})
    assert {d["stat"] for d in res.conformal} == {"mean", "max", "min", "spread", "evening"}
    for d in res.conformal:
        assert 0 <= d["raw80"] <= 1 and 0 <= d["conformal80"] <= 1
    (summary,) = summaries(led)
    assert summary["conformal"]["power"] == res.conformal


def test_experiments_page_renders_every_view_from_real_summaries(tmp_path, dom) -> None:
    """T136: champion/challenger (with tuned settings), timeline, importance, quantiles,
    conformal and drift all render from summaries the weekly job wrote."""
    pytest.importorskip("lightgbm")
    from arena.forecasters.ml_power_lgbm import train_lgbm
    from arena.site.build import build_site

    led = Ledger(tmp_path / "l")
    fams = {"hgb": trainer(dom),
            "lgbm": lambda c: train_lgbm(dom, c, n_trials=2, folds=1)}  # fmt: skip
    weekly(led, FixedClock(NOW), {"power": dom}, {"power": fams}, drift=True)
    (s,) = summaries(led)
    cands = {c["family"]: c for c in s["decisions"][0]["candidates"]}
    assert set(cands) == {"hgb", "lgbm"} and cands["lgbm"]["params"]  # Optuna's best trial
    res = build_site(led, tmp_path / "site", FixedClock(NOW))
    page = (res.out_dir / "experiments.html").read_text()
    for part in ("Model timeline", "Champion vs challengers", "Tuned settings",
                 "What drives the electricity model", "Conformal prediction intervals",
                 "Probabilistic accuracy"):  # fmt: skip
        assert part in page, part
    if s.get("drift"):
        assert "Drift (" in page
