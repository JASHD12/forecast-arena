"""Isolation Forest against a robust z-score on injected faults in real price windows (T294).

Windows are the 28 days ending on each day of the evaluation period, built from real day-ahead
prices. The detector threshold is chosen on clean windows of the training years only (the
`1 - target` quantile of the clean scores, so about `target` false alarms) and then evaluated on
later windows: the false-alarm rate on clean windows, and the share of injected faults caught.
Faults are applied to the latest day only: a spike (one hour times 8), a unit error (prices divided
by 1000), a flat feed (one value for 24 hours) and a repeated day (yesterday's hours again).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date, timedelta
from typing import Any

import numpy as np

from arena.domains.power import day_stats
from arena.forecasters.ml_power import context_rows
from arena.ops import anomaly

FAULTS = ("spike", "unit_error", "flat_feed", "repeated_day")


def inject(kind: str, daily: dict[date, list[float]], day: date) -> list[float]:
    """The hourly prices of `day` with one fault applied (the data itself is not changed)."""
    v = list(daily[day])
    if kind == "spike":
        i = int(np.argmax(np.abs(v)))
        v[i] = v[i] * 8 if v[i] else 400.0
    elif kind == "unit_error":
        v = [x / 1000 for x in v]
    elif kind == "flat_feed":
        v = [float(np.mean(v))] * len(v)
    elif kind == "repeated_day":
        v = list(daily[day - timedelta(days=1)])
    else:
        raise ValueError(kind)
    return v


def windows(daily: dict[date, list[float]], first: date, last: date, step: int = 3) -> list[date]:
    """Days in [first, last] (every `step`-th) whose 28-day window and previous day are known."""
    out, d = [], first
    while d <= last:
        if d in daily and (d - timedelta(days=1)) in daily:
            out.append(d)
        d += timedelta(days=step)
    return out


def rows_with(daily: dict[date, list[float]], day: date, hourly: list[float] | None) -> list[Any]:
    """Context rows ending on `day`, the last one replaced when `hourly` is given."""
    rows = context_rows(daily, day)
    if hourly is not None:
        rows[-1] = {"day": day.isoformat(), **day_stats(day, hourly)}
    return rows


def run(
    daily: dict[date, list[float]],
    train: tuple[date, date],
    test: tuple[date, date],
    target_fpr: float = 0.05,
    step: int = 3,
) -> dict[str, Any]:
    """Thresholds from clean training windows, then false alarms and detection per fault."""
    dets: dict[str, Callable[[Sequence[Any]], float]] = {
        "isolation_forest": anomaly.isolation_score,
        "robust_z": anomaly.robust_z,
    }
    clean_train = {
        k: [f(rows_with(daily, d, None)) for d in windows(daily, *train, step)]
        for k, f in dets.items()
    }
    thr = {k: float(np.quantile(v, 1 - target_fpr)) for k, v in clean_train.items()}
    days = windows(daily, *test, step)
    out: dict[str, Any] = {"threshold": thr, "n_windows": len(days), "metrics": {}}
    for k, f in dets.items():
        clean = [f(rows_with(daily, d, None)) > thr[k] for d in days]
        row: dict[str, float | int] = {
            "false_alarm_pct": round(100 * float(np.mean(clean)), 1),
            "n": len(days),
        }
        for fault in FAULTS:
            hit = [f(rows_with(daily, d, inject(fault, daily, d))) > thr[k] for d in days]
            row[f"{fault}_detected_pct"] = round(100 * float(np.mean(hit)), 1)
        out["metrics"][k] = row
    return out
