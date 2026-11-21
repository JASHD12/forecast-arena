"""Calibration methods compared on the power champion's backtest probabilities (T256).

The `ml` probabilities of a stored walk-forward backtest are re-calibrated after the fact, day by
day, with calibrators fitted only on strictly earlier batch days: identity (the champion as it is),
Platt (logistic on the logit), isotonic regression, and beta calibration (logistic on ln p and
ln(1-p)). All are scored on the same later days with a day-block interval for the paired Brier
difference against identity. It is an offline study; it never changes the live `ml` forecaster.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from arena.scoring import stats

EPS = 0.01


class Calibrator(Protocol):
    """Fit on earlier (probability, outcome) pairs; map new probabilities."""

    def fit(self, p: Sequence[float], y: Sequence[int]) -> None: ...

    def predict(self, p: Sequence[float]) -> list[float]: ...


def _clip(p: Sequence[float]) -> np.ndarray:
    return np.clip(np.asarray(p, float), EPS, 1 - EPS)


class Identity:
    """No re-calibration: the champion as it is."""

    def fit(self, p: Sequence[float], y: Sequence[int]) -> None:
        """Nothing to learn."""

    def predict(self, p: Sequence[float]) -> list[float]:
        """The clipped probabilities."""
        return [float(x) for x in _clip(p)]


class _Logistic:
    """Logistic regression on a feature map; falls back to identity with one outcome only."""

    def __init__(self) -> None:
        self._clf: LogisticRegression | None = None

    def features(self, p: np.ndarray) -> np.ndarray:  # pragma: no cover - overridden
        raise NotImplementedError

    def fit(self, p: Sequence[float], y: Sequence[int]) -> None:
        """Fit; keeps identity behaviour if the data has a single outcome."""
        self._clf = None
        if len(set(y)) < 2:
            return
        clf = LogisticRegression(C=1e6, max_iter=1000)
        clf.fit(self.features(_clip(p)), list(y))
        self._clf = clf

    def predict(self, p: Sequence[float]) -> list[float]:
        """Calibrated probabilities, clipped to [0.01, 0.99]."""
        x = _clip(p)
        if self._clf is None:
            return [float(v) for v in x]
        return [
            float(v) for v in np.clip(self._clf.predict_proba(self.features(x))[:, 1], EPS, 1 - EPS)
        ]


class Platt(_Logistic):
    """Logistic regression on the logit (Platt scaling)."""

    def features(self, p: np.ndarray) -> np.ndarray:
        """logit(p) as the only feature."""
        return np.log(p / (1 - p)).reshape(-1, 1)


class BetaCal(_Logistic):
    """Beta calibration: logistic regression on ln p and -ln(1-p) (Kull et al. 2017)."""

    def features(self, p: np.ndarray) -> np.ndarray:
        """Two features: ln p and -ln(1-p)."""
        return np.column_stack([np.log(p), -np.log(1 - p)])


class Isotonic:
    """Isotonic regression (monotone, piecewise constant)."""

    def __init__(self) -> None:
        self._iso: IsotonicRegression | None = None

    def fit(self, p: Sequence[float], y: Sequence[int]) -> None:
        """Fit a monotone map."""
        self._iso = IsotonicRegression(y_min=EPS, y_max=1 - EPS, out_of_bounds="clip")
        self._iso.fit(_clip(p), list(y))

    def predict(self, p: Sequence[float]) -> list[float]:
        """Map through the fitted step function."""
        if self._iso is None:
            return [float(v) for v in _clip(p)]
        return [float(v) for v in self._iso.predict(_clip(p))]


def load_rows(run_dir: Path, forecaster: str = "ml") -> list[dict[str, Any]]:
    """The backtest rows of one forecaster, sorted by (batch_date, question_id)."""
    rows = []
    for line in (run_dir / "forecasts.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["forecaster_id"] == forecaster:
            rows.append(
                {
                    "day": r["batch_date"],
                    "id": r["question_id"],
                    "p": float(r["probability"]),
                    "y": int(r["outcome"]),
                }
            )
    return sorted(rows, key=lambda r: (r["day"], r["id"]))


def walk_forward(
    rows: Sequence[Mapping[str, Any]],
    methods: Mapping[str, Calibrator],
    *,
    warmup_days: int = 120,
    refit_every: int = 7,
) -> dict[str, dict[str, list[Any]]]:
    """Out-of-sample probabilities per method on every day after the warm-up.

    A calibrator used on day d is fitted on rows of batch days strictly before d (outcomes known).
    """
    by_day: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r)
    days = sorted(by_day)
    out: dict[str, dict[str, list[Any]]] = {m: {"day": [], "p": [], "y": []} for m in methods}
    seen_p: list[float] = []
    seen_y: list[int] = []
    last_fit = -refit_every
    for i, d in enumerate(days):
        if i >= warmup_days:
            if i - last_fit >= refit_every:
                for cal in methods.values():
                    cal.fit(seen_p, seen_y)
                last_fit = i
            ps = [r["p"] for r in by_day[d]]
            ys = [r["y"] for r in by_day[d]]
            for m, cal in methods.items():
                out[m]["p"].extend(cal.predict(ps))
                out[m]["y"].extend(ys)
                out[m]["day"].extend([d] * len(ps))
        seen_p.extend(r["p"] for r in by_day[d])
        seen_y.extend(r["y"] for r in by_day[d])
    return out


def summarize(
    preds: Mapping[str, Mapping[str, Sequence[Any]]], baseline: str = "identity"
) -> tuple[dict[str, dict[str, float | int]], list[dict[str, Any]]]:
    """Brier and ECE per method, and the paired Brier difference against `baseline`."""
    metrics: dict[str, dict[str, float | int]] = {}
    paired: list[dict[str, Any]] = []
    base = preds[baseline]
    for m, d in preds.items():
        p, y = list(d["p"]), list(d["y"])
        metrics[m] = {
            "n": len(p),
            "brier": round(float(np.mean(stats.brier_terms(p, y))), 4),
            "ece": round(stats.expected_calibration_error(p, y), 4),
        }
        if m != baseline:
            iv = stats.paired_brier_difference(list(d["day"]), p, list(base["p"]), y)
            paired.append(
                {
                    "a": m,
                    "b": baseline,
                    "diff": iv.estimate,
                    "lo": iv.low,
                    "hi": iv.high,
                    "n": iv.n,
                    "days": iv.days,
                }
            )
    return metrics, paired


def default_methods() -> dict[str, Calibrator]:
    """The four compared calibrators."""
    return {"identity": Identity(), "platt": Platt(), "isotonic": Isotonic(), "beta": BetaCal()}


def finite(x: float) -> bool:
    """True for finite floats (used by tests on the result)."""
    return math.isfinite(x)
