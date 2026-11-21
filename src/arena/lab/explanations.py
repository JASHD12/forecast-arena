"""Per-forecast explanations for the power model (T260).

Model-agnostic occlusion: each feature (or a small named group) of a question's input is replaced
by its typical value (the median over recent days) and the change in the final probability is
recorded. The three largest changes are the explanation. It works for any model with the
`PowerModel` interface (histogram boosting and LightGBM alike), needs no extra package, and is an
attribution of this model's behaviour, not a causal statement about the market.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

import numpy as np

from arena.forecasters.ml_power import STATS, PowerModel, _logit, cdf_at

_PER_STAT = (
    "yesterday",
    "last 7 days, mean",
    "28 days, median",
    "last 7 days, spread",
    "same weekday last week",
)
_CALENDAR = (
    ("weekday", range(0, 7)),
    ("season", range(7, 9)),
    ("holiday today", [9]),
    ("holiday yesterday", [10]),
    ("days since last data", [11]),
)


def groups() -> list[tuple[str, list[int]]]:
    """Named groups of feature columns: calendar parts, then five per statistic."""
    out: list[tuple[str, list[int]]] = [(n, list(ix)) for n, ix in _CALENDAR]
    for i, stat in enumerate(STATS):
        for j, label in enumerate(_PER_STAT):
            out.append((f"{stat}: {label}", [12 + 5 * i + j]))
    return out


def background(rows: Sequence[Sequence[float]]) -> np.ndarray:
    """The typical input: the median of each feature over recent days."""
    return np.median(np.asarray(rows, float), axis=0)


def probability_from(
    model: PowerModel, stat: str, x: Sequence[float], threshold: float, comparator: str
) -> float:
    """Calibrated P(YES) for a feature vector (the model's own pipeline, on a given input)."""
    f = cdf_at(model.quantiles(stat, list(x)), threshold)
    raw = f if comparator == "lt" else 1 - f
    if model.calib is None:
        return raw
    return float(model.calib.predict_proba([[_logit(raw)]])[0, 1])


def explain(
    model: PowerModel,
    stat: str,
    x: Sequence[float],
    threshold: float,
    comparator: str,
    typical: np.ndarray,
    top: int = 3,
) -> dict[str, Any]:
    """Probability and the `top` groups whose occlusion changes it most (signed, in points)."""
    base = probability_from(model, stat, x, threshold, comparator)
    effects = []
    for name, idx in groups():
        z = np.asarray(x, float).copy()
        z[idx] = typical[idx]
        delta = base - probability_from(model, stat, z.tolist(), threshold, comparator)
        effects.append((name, delta))
    effects.sort(key=lambda t: -abs(t[1]))
    return {
        "probability": base,
        "top": [{"feature": n, "effect_points": round(100 * d, 1)} for n, d in effects[:top]],
    }


def example_rows(
    model: PowerModel, domain: Any, batch: date, asof: Any, limit: int = 3
) -> list[dict[str, Any]]:
    """Explanations for the first `limit` questions of a batch day (typical-input background)."""
    from arena.forecasters.ml_power import features

    qs = domain.generate_questions(batch, asof)[:limit]
    out = []
    for q in qs:
        ctx = domain.context(q, asof)
        rows = [
            features(ctx["daily"][: k + 1], q.target_date)
            for k in range(len(ctx["daily"]) - 7, len(ctx["daily"]))
        ]
        x = features(ctx["daily"], q.target_date)
        thr = float(q.params["reference_mean"]) if q.template == "up_vs_today" else q.threshold
        assert thr is not None
        out.append(
            {
                "question": q.text,
                **explain(model, str(q.params["stat"]), x, thr, q.comparator, background(rows)),
            }
        )
    return out
