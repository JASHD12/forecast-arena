"""The data chart on a question page (T131): the series the forecasters saw at forecast
time (from the morning snapshot), the question's threshold, and the observed value.

Only data from the as-of context is plotted, plus the published observed value once the
question is resolved, so the chart shows exactly what was known and what happened.
"""

from __future__ import annotations

import html
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from markupsafe import Markup

from arena.models import Question

W, H = 640, 240
PAD = (14, 16, 30, 54)  # top, right, bottom, left


@dataclass
class ChartData:
    """What to draw."""

    title: str
    unit: str
    series: list[tuple[str, list[tuple[str, float]]]] = field(default_factory=list)
    reference: tuple[float, str] | None = None
    observed: float | None = None
    target_day: str = ""


def _points(rows: Sequence[dict[str, Any]], key: str, value: str) -> list[tuple[str, float]]:
    out = []
    for r in rows:
        v = r.get(value)
        if isinstance(v, int | float) and math.isfinite(v):
            out.append((str(r[key]), float(v)))
    return out


def _weather_var(template: str) -> str:
    if "gust" in template:
        return "gust_max"
    if "tmin" in template or "frost" in template:
        return "tmin"
    if "wet" in template or "rain" in template or "precip" in template:
        return "precip"
    return "tmax"


def chart_data(q: Question, ctx: dict[str, Any], observed: float | None) -> ChartData | None:
    """The chart for a question, or None when its context has no plottable series."""
    td = q.target_date.isoformat()
    thr = q.params.get("reference_mean") if q.template == "up_vs_today" else q.threshold
    ref = None if thr is None else (float(thr), "threshold")
    if q.domain == "power":
        stat = str(q.params.get("stat", "mean"))
        pts = _points(ctx.get("daily", []), "day", stat)
        return ChartData(f"Daily {stat} price", q.unit, [(stat, pts)], ref, observed, td)
    if q.domain == "weather":
        var = _weather_var(q.template)
        if "city_a" in ctx:
            series = []
            for k in ("city_a", "city_b"):
                rows = ctx[k].get("observed_daily", [])
                series.append((str(q.params.get(k, k)), _points(rows, "day", var)))
            return ChartData(f"Observed {var}", q.unit, series, None, None, td)
        pts = _points(ctx.get("observed_daily", []), "day", var)
        return ChartData(
            f"Observed {var} at {ctx.get('station', q.entity)}",
            q.unit,
            [(var, pts)],
            ref,
            observed,
            td,
        )
    if q.domain == "attention":
        pts = _points(ctx.get("daily_views", []), "day", "views")
        return ChartData("Daily page views", "views", [("views", pts)], ref, observed, td)
    if q.domain == "markets":  # the question is about a change, so no level threshold
        pts = _points(ctx.get("fixings", []), "day", "rate")
        return ChartData(f"ECB reference rate {q.entity}", "rate", [("rate", pts)], None, None, td)
    if q.domain == "crypto":
        pts = _points(ctx.get("daily_usd_00utc", []), "day", "price")
        return ChartData("Daily price at 00:00 UTC", "USD", [("price", pts)], None, None, td)
    return None


def _fmt(v: float) -> str:
    a = abs(v)
    if a >= 1000:
        return f"{v:,.0f}"
    if a >= 10:
        return f"{v:.0f}"
    if a >= 1:
        return f"{v:.2f}"
    return f"{v:.4f}"


def series_svg(cd: ChartData) -> Markup:
    """A small line chart; days on x (target day last when observed), values on y."""
    days = sorted({d for _, pts in cd.series for d, _ in pts})
    if cd.observed is not None and cd.target_day not in days:
        days.append(cd.target_day)
    vals = [v for _, pts in cd.series for _, v in pts]
    vals += [x for x in (cd.reference[0] if cd.reference else None, cd.observed) if x is not None]
    if not days or not vals:
        return Markup("")
    lo, hi = min(vals), max(vals)
    if hi == lo:
        lo, hi = lo - 1, hi + 1
    pad = (hi - lo) * 0.08
    lo, hi = lo - pad, hi + pad
    top, right, bottom, left = PAD
    w, h = W - left - right, H - top - bottom
    n = max(1, len(days) - 1)
    ix = {d: i for i, d in enumerate(days)}

    def x(d: str) -> float:
        return left + ix[d] / n * w

    def y(v: float) -> float:
        return top + h - (v - lo) / (hi - lo) * h

    e = html.escape
    p = [
        f'<svg class="qchart" viewBox="0 0 {W} {H}" role="img" aria-labelledby="qc-t qc-d">',
        f'<title id="qc-t">{e(cd.title)}</title>',
        f'<desc id="qc-d">{e(cd.title)} in {e(cd.unit)} as known at forecast time'
        f"{', with the threshold' if cd.reference else ''}"
        f"{' and the observed value' if cd.observed is not None else ''}. "
        "The values are also in the table below.</desc>",
    ]
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        p.append(
            f'<line class="grid" x1="{left}" x2="{left + w}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
        )
        p.append(
            f'<text class="tick" x="{left - 6}" y="{y(v) + 4:.1f}" text-anchor="end">'
            f"{e(_fmt(v))}</text>"
        )
    for d in (days[0], days[-1]):
        p.append(
            f'<text class="tick" x="{x(d):.1f}" y="{H - 8}" text-anchor="middle">{e(d[5:])}</text>'
        )
    if cd.reference:
        ry = y(cd.reference[0])
        p.append(
            f'<line class="ref-line" x1="{left}" x2="{left + w}" y1="{ry:.1f}" y2="{ry:.1f}"/>'
        )
        label = f"{e(cd.reference[1])} {e(_fmt(cd.reference[0]))}"
        p.append(
            f'<text class="tick ref-label" x="{left + 6}" y="{ry - 5:.1f}" '
            f'text-anchor="start">{label}</text>'
        )
    for i, (name, pts) in enumerate(cd.series):
        if not pts:
            continue
        path = " ".join(
            f"{'M' if j == 0 else 'L'}{x(d):.1f},{y(v):.1f}" for j, (d, v) in enumerate(pts)
        )
        p.append(f'<path class="qline s-{i + 1}" d="{path}"><title>{e(name)}</title></path>')
        for d, v in pts:
            p.append(
                f'<circle class="qdot s-{i + 1}" cx="{x(d):.1f}" cy="{y(v):.1f}" r="2.5">'
                f"<title>{e(d)}: {e(_fmt(v))}</title></circle>"
            )
    if cd.observed is not None:
        ox, oy = x(cd.target_day), y(cd.observed)
        label = f"observed on {e(cd.target_day)}: {e(_fmt(cd.observed))}"
        p.append(
            f'<circle class="qobs" cx="{ox:.1f}" cy="{oy:.1f}" r="5">'
            f"<title>{label}</title></circle>"
        )
    p.append("</svg>")
    return Markup("".join(p))
