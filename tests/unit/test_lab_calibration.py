"""T256: calibrators, walk-forward without leakage, and the committed result."""

import json
from pathlib import Path

import numpy as np
import pytest

from arena.lab import calibration_study as cs

ROOT = Path(__file__).resolve().parents[2]


def _rows(n_days: int = 30, per_day: int = 6, seed: int = 0, over: float = 0.0):
    """Probabilities that are over-confident by `over` (true rate is closer to 0.5)."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_days):
        for k in range(per_day):
            p = float(rng.uniform(0.05, 0.95))
            true = 0.5 + (p - 0.5) * (1 - over)
            rows.append({"day": f"2026-01-{d + 1:02d}", "id": f"q{d}-{k}", "p": p,
                         "y": int(rng.random() < true)})  # fmt: skip
    return rows


def test_identity_clips_and_single_outcome_falls_back() -> None:
    assert cs.Identity().predict([0.0, 0.5, 1.0]) == [0.01, 0.5, 0.99]
    for cal in (cs.Platt(), cs.BetaCal()):
        cal.fit([0.2, 0.8], [1, 1])  # one outcome only: stays identity
        assert cal.predict([0.3]) == pytest.approx([0.3])


def test_calibrators_pull_overconfident_probabilities_towards_the_middle() -> None:
    rows = _rows(n_days=200, over=0.6, seed=1)
    p, y = [r["p"] for r in rows], [r["y"] for r in rows]
    for cal in (cs.Platt(), cs.BetaCal(), cs.Isotonic()):
        cal.fit(p, y)
        lo, hi = cal.predict([0.05, 0.95])
        assert 0.01 <= lo < hi <= 0.99
        assert lo > 0.05, type(cal).__name__
    for cal in (cs.Platt(), cs.BetaCal()):  # isotonic can still over-fit the sparse top bin
        cal.fit(p, y)
        assert cal.predict([0.95])[0] < 0.95


def test_isotonic_is_monotone() -> None:
    rows = _rows(n_days=100, seed=2)
    cal = cs.Isotonic()
    cal.fit([r["p"] for r in rows], [r["y"] for r in rows])
    out = cal.predict(list(np.linspace(0.01, 0.99, 50)))
    assert out == sorted(out)


class Spy:
    """Records the days it was fitted on."""

    def __init__(self) -> None:
        self.fitted_on: list[int] = []

    def fit(self, p, y) -> None:
        self.fitted_on.append(len(p))

    def predict(self, p):
        return [0.5] * len(p)


def test_walk_forward_fits_only_on_earlier_days() -> None:
    rows = _rows(n_days=20, per_day=6)
    spy = Spy()
    out = cs.walk_forward(rows, {"spy": spy}, warmup_days=5, refit_every=3)
    # first fit happens on day index 5, using exactly the 5 earlier days (30 rows)
    assert spy.fitted_on == [30, 48, 66, 84, 102]  # every fit sees only days before its own day
    assert len(out["spy"]["p"]) == 15 * 6  # only days after the warm-up are scored
    assert min(out["spy"]["day"]) == "2026-01-06"


def test_summary_pairs_against_identity() -> None:
    rows = _rows(n_days=60, over=0.6, seed=3)
    preds = cs.walk_forward(rows, cs.default_methods(), warmup_days=20)
    metrics, paired = cs.summarize(preds)
    assert set(metrics) == {"identity", "platt", "isotonic", "beta"}
    assert {p["a"] for p in paired} == {"platt", "isotonic", "beta"}
    assert all(p["b"] == "identity" and p["lo"] <= p["diff"] <= p["hi"] for p in paired)
    # over-confident inputs: Platt must beat identity on Brier
    assert metrics["platt"]["brier"] < metrics["identity"]["brier"]


def test_committed_result_is_consistent() -> None:
    path = ROOT / "evals" / "results" / "lab-calibration.json"
    if not path.is_file():
        pytest.skip("calibration result not committed in this checkout")
    r = json.loads(path.read_text())
    assert set(r["metrics"]) == {"identity", "platt", "isotonic", "beta"}
    assert all(cs.finite(p["diff"]) for p in r["paired"]) and r["cost_usd"] == 0
