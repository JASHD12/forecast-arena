"""Model explainability for the weekly job: permutation feature importance.

Owner request 2026-11-12 (DECISIONS.md "Explainability"). For the promoted power model,
the median quantile regressor of the daily mean price is evaluated on the weekly window's
target days; each feature column is shuffled `REPEATS` times and the increase in mean
absolute error is its importance (scikit-learn `permutation_importance`, fixed seed).
Model-agnostic, honest about uncertainty (mean and standard deviation over repeats), and
computed on data the model was not fitted on when the window lies after its cut-off.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sklearn.inspection import permutation_importance

from arena.domains.power import PowerDomain
from arena.forecasters.ml_power import training_rows
from arena.ops.drift import FEATURE_NAMES

REPEATS = 10
TOP = 8
MIN_ROWS = 7


def power_importance(
    domain: PowerDomain, model: Any, first: date, last: date
) -> list[dict[str, Any]]:
    """Top features by permutation importance (MAE increase in EUR/MWh); [] if too few
    rows or no median `mean` regressor."""
    models = getattr(model, "models", {})
    if "mean" not in models or not models["mean"]:
        return []
    x, ys, _ = training_rows(domain.all_days(), first, last)
    if len(x) < MIN_ROWS:
        return []
    est = models["mean"][len(models["mean"]) // 2]
    r = permutation_importance(
        est, x, ys["mean"], scoring="neg_mean_absolute_error", n_repeats=REPEATS,
        random_state=0,
    )  # fmt: skip
    rows: list[dict[str, Any]] = [
        {
            "feature": FEATURE_NAMES[i],
            "mae_increase": round(float(m), 4),
            "std": round(float(s), 4),
        }
        for i, (m, s) in enumerate(zip(r.importances_mean, r.importances_std, strict=True))
    ]
    rows.sort(key=lambda d: float(d["mae_increase"]), reverse=True)
    return rows[:TOP]
