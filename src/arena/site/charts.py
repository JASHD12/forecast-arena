"""Inline SVG charts (no JavaScript). Colours come from CSS variables, so both themes work;
every chart has a <title>/<desc>, native tooltips on marks, and a data table next to it."""

from __future__ import annotations

import math
from collections.abc import Sequence
from html import escape
from typing import Any

from markupsafe import Markup

from arena.scoring.stats import Bin

SIZE = 240
PAD = 36


def reliability_svg(name: str, bins: Sequence[Bin]) -> Markup:
    """Reliability diagram: mean forecast (x) vs observed frequency (y), diagonal = ideal.

    Marker area does not encode count (the table gives n); identity is in the title."""
    inner = SIZE - 2 * PAD

    def x(v: float) -> float:
        return PAD + v * inner

    def y(v: float) -> float:
        return SIZE - PAD - v * inner

    parts = [
        f'<svg class="chart" viewBox="0 0 {SIZE} {SIZE}" role="img" '
        f'aria-labelledby="t-{escape(name)} d-{escape(name)}">',
        f'<title id="t-{escape(name)}">Reliability diagram: {escape(name)}</title>',
        f'<desc id="d-{escape(name)}">Observed frequency of YES against the mean forecast in '
        f"{len(bins)} bins; points on the dashed diagonal are perfectly calibrated.</desc>",
    ]
    for t in (0.0, 0.5, 1.0):
        parts.append(f'<line class="grid" x1="{x(t)}" y1="{y(0)}" x2="{x(t)}" y2="{y(1)}"/>')
        parts.append(f'<line class="grid" x1="{x(0)}" y1="{y(t)}" x2="{x(1)}" y2="{y(t)}"/>')
        parts.append(
            f'<text class="tick" x="{x(t)}" y="{SIZE - PAD + 14}" text-anchor="middle">{t:g}</text>'
        )
        parts.append(
            f'<text class="tick" x="{PAD - 6}" y="{y(t) + 4}" text-anchor="end">{t:g}</text>'
        )
    parts.append(f'<line class="ideal" x1="{x(0)}" y1="{y(0)}" x2="{x(1)}" y2="{y(1)}"/>')
    pts = [(x(b.mean_forecast), y(b.observed_rate), b) for b in bins]
    if len(pts) > 1:
        path = " ".join(
            f"{'M' if i == 0 else 'L'}{px:.1f},{py:.1f}" for i, (px, py, _) in enumerate(pts)
        )
        parts.append(f'<path class="series" d="{path}"/>')
    for px, py, b in pts:
        parts.append(
            f'<circle class="mark" cx="{px:.1f}" cy="{py:.1f}" r="5"><title>'
            f"forecast {b.mean_forecast:.2f}, observed {b.observed_rate:.2f}, "
            f"n={b.n}</title></circle>"
        )
    parts.append(
        f'<text class="axis" x="{SIZE / 2}" y="{SIZE - 4}" text-anchor="middle">'
        "mean forecast</text>"
    )
    parts.append(
        f'<text class="axis" transform="translate(11 {SIZE / 2}) rotate(-90)" '
        'text-anchor="middle">observed frequency</text>'
    )
    parts.append("</svg>")
    return Markup("".join(parts))


#: Fixed colour per forecaster (identity, never rank). Categorical slots validated with the
#: dataviz palette script (light and dark); the base rate is the neutral reference line.
SERIES_SLOTS = {
    "ml": 1,
    "llm_plain": 2,
    "llm_context": 3,
    "agent": 4,
    "persistence": 5,
    "ensemble": 6,
    "human_panel": 7,
}
RACE_W, RACE_H = 680, 300
RACE_PAD = (16, 150, 30, 44)  # top, right, bottom, left


def series_class(fid: str) -> str:
    """CSS class carrying the forecaster's colour."""
    if fid == "base_rate":
        return "s-ref"
    return f"s-{SERIES_SLOTS.get(fid, 8)}"


def race_svg(
    series: dict[str, list[tuple[str, float]]], names: dict[str, str], days: Sequence[str]
) -> Markup:
    """Line chart of cumulative mean Brier score per forecaster over batch days.

    One y-axis (Brier, lower is better), a hairline reference at 0.25 (always saying 50%),
    2px lines, end dots with direct labels, and a native tooltip on every point."""
    top, right, bottom, left = RACE_PAD
    w, h = RACE_W - left - right, RACE_H - top - bottom
    vals = [v for pts in series.values() for _, v in pts] + [0.25]  # keep the coin line
    step = 0.05 if max(vals) - min(vals) > 0.12 else 0.02
    ymin = max(0.0, math.floor((min(vals) - step / 2) / step) * step)
    ymax = math.ceil((max(vals) + step / 2) / step) * step
    idx = {d: i for i, d in enumerate(days)}
    n = max(1, len(days) - 1)

    def x(d: str) -> float:
        return left + (idx[d] / n) * w if len(days) > 1 else left + w / 2

    def y(v: float) -> float:
        return top + h - ((v - ymin) / (ymax - ymin)) * h

    p = [
        f'<svg class="race" viewBox="0 0 {RACE_W} {RACE_H}" role="img" '
        'aria-labelledby="race-t race-d">',
        '<title id="race-t">Cumulative Brier score by forecaster</title>',
        '<desc id="race-d">Running average Brier score (lower is better) after each batch '
        "day, on the questions every plotted forecaster answered. The data is also in the "
        "table below the chart.</desc>",
    ]
    t = ymin
    while t <= ymax + 1e-9:
        p.append(
            f'<line class="grid" x1="{left}" x2="{left + w}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
        )
        p.append(
            f'<text class="tick" x="{left - 8}" y="{y(t) + 4:.1f}" text-anchor="end">{t:.2f}</text>'
        )
        t = round(t + step, 10)
    p.append(
        f'<line class="coinline" x1="{left}" x2="{left + w}" '
        f'y1="{y(0.25):.1f}" y2="{y(0.25):.1f}"/>'
    )
    p.append(f'<text class="tick" x="{left + 4}" y="{y(0.25) - 5:.1f}">coin flip (0.25)</text>')
    for d in (days[0], days[-1]) if days else ():
        anchor = "start" if d == days[0] else "end"
        p.append(
            f'<text class="tick" x="{x(d):.1f}" y="{RACE_H - 8}" '
            f'text-anchor="{anchor}">{escape(d)}</text>'
        )
    ends: list[list[Any]] = []
    for fid, pts in series.items():
        if not pts:
            continue
        cls = series_class(fid)
        path = " ".join(
            f"{'M' if i == 0 else 'L'}{x(d):.1f},{y(v):.1f}" for i, (d, v) in enumerate(pts)
        )
        p.append(f'<path class="line {cls}" d="{path}"/>')
        for d, v in pts:
            tip = escape(f"{names.get(fid, fid)}: {v:.3f} after {d}")
            p.append(
                f'<g class="pt"><circle class="hit" cx="{x(d):.1f}" cy="{y(v):.1f}" r="10">'
                f"<title>{tip}</title></circle>"
                f'<circle class="dot {cls}" cx="{x(d):.1f}" cy="{y(v):.1f}" r="3.5"/></g>'
            )
        d_last, v_last = pts[-1]
        ends.append([y(v_last), x(d_last), fid, v_last])
    ends.sort()
    for i in range(1, len(ends)):  # keep end labels at least 15px apart
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 15)
    for ly, _lx, fid, v in ends:
        p.append(
            f'<text class="endlabel" x="{left + w + 10}" y="{ly + 4:.1f}">'
            f"{escape(names.get(fid, fid))} {v:.3f}</text>"
        )
    p.append("</svg>")
    return Markup("".join(p))
