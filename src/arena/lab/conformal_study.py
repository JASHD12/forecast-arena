"""Conformal coverage study for the power model's price bands (T257).

For each calendar month a model is trained on days before a calibration window, a CQR margin
(Romano et al., 2019) is fitted on the 30 days before the month, and the central 80% and 90%
bands are scored on the month itself: empirical coverage raw and after the margin, and the mean
band width. Nothing here changes a live forecaster; the same margin idea runs live only as the
experimental interval of T276b.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

import numpy as np

from arena.domains.power import PowerDomain
from arena.forecasters.ml_power import QUANTILES, STATS, train, training_rows
from arena.ops.explain import cqr_margin

BANDS = {
    80: (QUANTILES.index(0.1), QUANTILES.index(0.9)),
    90: (QUANTILES.index(0.05), QUANTILES.index(0.95)),
}
CAL_DAYS = 30
MIN_ROWS = 20


def month_windows(first: date, last: date) -> list[tuple[date, date]]:
    """(first day, last day) of each calendar month from `first`'s month to `last`'s month."""
    out, d = [], date(first.year, first.month, 1)
    while d <= last:
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        out.append((d, nxt - timedelta(days=1)))
        d = nxt
    return out


def _inside(lo: np.ndarray, hi: np.ndarray, y: np.ndarray, margin: float) -> float:
    """Share of observations inside [lo - margin, hi + margin]."""
    return round(float(np.mean((lo - margin <= y) & (y <= hi + margin))), 3)


def coverage_rows(
    domain: PowerDomain,
    months: Sequence[tuple[date, date]],
    *,
    stats: Sequence[str] = STATS,
    **fit: Any,
) -> list[dict[str, Any]]:
    """One row per (month, statistic): raw and conformal coverage and width of both bands."""
    daily = domain.all_days()
    rows: list[dict[str, Any]] = []
    for first, last in months:
        cal = (first - timedelta(days=CAL_DAYS), first - timedelta(days=1))
        model = train(domain, cal[0] - timedelta(days=1), **fit)
        xc, yc, _ = training_rows(daily, *cal)
        xe, ye, _ = training_rows(daily, first, last)
        if len(xc) < MIN_ROWS or len(xe) < MIN_ROWS:
            continue
        for stat in stats:
            qc = np.array([sorted(model.quantiles(stat, list(r))) for r in xc])
            qe = np.array([sorted(model.quantiles(stat, list(r))) for r in xe])
            row: dict[str, Any] = {"month": first.strftime("%Y-%m"), "stat": stat, "n": len(xe)}
            for pct, (lo, hi) in BANDS.items():
                m = cqr_margin(qc[:, lo], qc[:, hi], yc[stat], pct / 100)
                row[f"raw{pct}"] = _inside(qe[:, lo], qe[:, hi], ye[stat], 0.0)
                row[f"conformal{pct}"] = _inside(qe[:, lo], qe[:, hi], ye[stat], m)
                row[f"width{pct}"] = round(float(np.mean(qe[:, hi] - qe[:, lo])) + 2 * m, 1)
            rows.append(row)
    return rows


def summarise(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, float | int | str | None]]:
    """Overall coverage per statistic (n-weighted over months) for the result file."""
    out: dict[str, dict[str, float | int | str | None]] = {}
    for stat in STATS:
        sel = [r for r in rows if r["stat"] == stat]
        if not sel:
            continue
        n = sum(r["n"] for r in sel)
        agg: dict[str, float | int | str | None] = {"n": n, "months": len(sel)}
        for key in ("raw80", "conformal80", "raw90", "conformal90"):
            agg[key] = round(sum(r[key] * r["n"] for r in sel) / n, 3)
        out[stat] = agg
    return out
