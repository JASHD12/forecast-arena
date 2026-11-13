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

import numpy as np
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


def pinball(y: float, q_pred: float, tau: float) -> float:
    """Pinball (quantile) loss of one prediction at level tau."""
    d = y - q_pred
    return max(tau * d, (tau - 1) * d)


def power_quantile_diagnostics(
    domain: PowerDomain, model: Any, first: date, last: date
) -> list[dict[str, Any]]:
    """Per daily statistic: mean pinball loss over all quantile levels (EUR/MWh; a
    discrete approximation of half the CRPS) and the empirical coverage of the central 80%
    and 90% prediction intervals on the window's target days. [] if too few rows."""
    from arena.forecasters.ml_power import QUANTILES, STATS

    if not hasattr(model, "quantiles"):
        return []
    x, ys, _ = training_rows(domain.all_days(), first, last)
    if len(x) < MIN_ROWS:
        return []
    i10, i90 = QUANTILES.index(0.1), QUANTILES.index(0.9)
    i05, i95 = QUANTILES.index(0.05), QUANTILES.index(0.95)
    out = []
    for stat in STATS:
        losses, in80, in90 = [], 0, 0
        for row, y in zip(x, ys[stat], strict=True):
            qv = sorted(model.quantiles(stat, list(row)))  # rearrangement: no crossing
            losses.append(
                sum(pinball(float(y), q, t) for q, t in zip(qv, QUANTILES, strict=True))
                / len(QUANTILES)
            )
            in80 += int(qv[i10] <= y <= qv[i90])
            in90 += int(qv[i05] <= y <= qv[i95])
        n = len(losses)
        out.append(
            {
                "stat": stat,
                "n": n,
                "pinball": round(sum(losses) / n, 3),
                "coverage80": round(in80 / n, 3),
                "coverage90": round(in90 / n, 3),
            }
        )
    return out


def power_shap(domain: PowerDomain, model: Any, first: date, last: date) -> list[dict[str, Any]]:
    """Top features by mean |SHAP value| (EUR/MWh) of the median regressor of the daily
    mean price on the window's target days, from SHAP's TreeExplainer. Only for tree models
    SHAP supports exactly (the LightGBM family); [] otherwise or if SHAP is missing."""
    from arena.forecasters.ml_power_lgbm import FAMILY as LGBM_FAMILY

    if getattr(model, "family", None) != LGBM_FAMILY:
        return []
    try:
        import shap
    except ImportError:
        return []
    models = getattr(model, "models", {})
    if not models.get("mean"):
        return []
    x, _, _ = training_rows(domain.all_days(), first, last)
    if len(x) < MIN_ROWS:
        return []
    est = models["mean"][len(models["mean"]) // 2]
    values = np.asarray(shap.TreeExplainer(est).shap_values(x))
    mean_abs = np.abs(values).mean(axis=0)
    rows: list[dict[str, Any]] = [{"feature": FEATURE_NAMES[i], "mean_abs_shap": round(float(v), 4)}
            for i, v in enumerate(mean_abs)]  # fmt: skip
    rows.sort(key=lambda d: float(d["mean_abs_shap"]), reverse=True)
    return rows[:TOP]
