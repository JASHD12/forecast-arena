"""Weekly drift report (SPEC 12, T081) with Evidently.

Compares the power model's input features and its median prediction on the evaluation
window (current) against the year before the window (reference). The computed metrics go
into the weekly summary on the ledger and onto the Experiments page; the full Evidently
HTML (large, interactive) is written next to the MLflow store for upload as a workflow
artifact, not to the ledger or the site. Evidently's telemetry is switched off.
Performance over time is the series of weekly Brier scores in the summaries.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from arena.domains.power import PowerDomain
from arena.forecasters.ml_power import STATS, training_rows

FEATURE_NAMES = (
    [f"weekday_{k}" for k in range(7)]
    + ["season_sin", "season_cos", "holiday_target", "holiday_last", "gap_days"]
    + [f"{s}_{f}" for s in STATS for f in ("last", "mean7", "median28", "std7", "week_ago")]
)
REFERENCE_DAYS = 365


def power_drift(
    domain: PowerDomain, model: Any, first: date, last: date, html_out: Path | None = None
) -> list[dict[str, Any]]:
    """Evidently data-drift metrics for the power features and the median prediction.

    Returns [] when Evidently is not installed (the weekly job still runs)."""
    os.environ.setdefault("DO_NOT_TRACK", "1")
    os.environ.setdefault("ITERATIVE_DO_NOT_TRACK", "1")
    try:
        import pandas as pd
        from evidently import Report
        from evidently.presets import DataDriftPreset
    except ImportError:
        return []
    daily = domain.all_days()
    ref_x, _, _ = training_rows(
        daily, first - timedelta(days=REFERENCE_DAYS), first - timedelta(days=1)
    )
    cur_x, _, _ = training_rows(daily, first, last)
    if len(ref_x) < 30 or len(cur_x) < 7:
        return []
    ref = pd.DataFrame(ref_x, columns=FEATURE_NAMES)
    cur = pd.DataFrame(cur_x, columns=FEATURE_NAMES)
    keep = [c for c in FEATURE_NAMES if not c.startswith(("weekday_", "holiday_"))]
    ref, cur = ref[keep].copy(), cur[keep].copy()
    if hasattr(model, "models") and "mean" in getattr(model, "models", {}):
        mid = len(model.models["mean"]) // 2
        ref["prediction_mean_median"] = model.models["mean"][mid].predict(ref_x)
        cur["prediction_mean_median"] = model.models["mean"][mid].predict(cur_x)
    snap = Report([DataDriftPreset()]).run(cur, ref)
    if html_out is not None:
        html_out.parent.mkdir(parents=True, exist_ok=True)
        snap.save_html(str(html_out))
    out = []
    for m in snap.dict().get("metrics", []):
        name = str(m.get("metric_name") or m.get("metric_id"))
        value = m.get("value")
        if isinstance(value, dict):
            value = ", ".join(
                f"{k}={v:.3g}" if isinstance(v, float) else f"{k}={v}" for k, v in value.items()
            )
        elif isinstance(value, float):
            value = f"{value:.4g}"
        out.append({"domain": "power", "metric": name, "value": str(value)})
    return out
