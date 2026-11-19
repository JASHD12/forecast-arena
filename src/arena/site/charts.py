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
    "agent_graph": 8,
    "llm_local": 6,  # shares the ensemble slot until T134 adds a validated ninth colour
}
RACE_MIN_DAYS = 7  # a line chart over fewer days is noise, not a race
RACE_WIDE = (700, 300, (16, 220, 34, 44))  # viewBox width, height, pad (top, right, bottom, left)
RACE_NARROW = (360, 300, (16, 12, 34, 40))  # phones: text in viewBox units stays readable
AI_FORECASTERS = ("llm_plain", "llm_context", "agent", "agent_graph", "llm_local")
RACE_LABEL_CHARS = 20  # longest name drawn next to a line (the legend has the full name)
HIGHLIGHT = ("ml", "base_rate")


def series_class(fid: str) -> str:
    """CSS class carrying the forecaster's colour."""
    if fid == "base_rate":
        return "s-ref"
    return f"s-{SERIES_SLOTS.get(fid, 8)}"


def _day_ticks(days: Sequence[str], limit: int) -> list[str]:
    """At most `limit` evenly spread days, always including the first and the last."""
    if len(days) <= limit:
        return list(days)
    step = (len(days) - 1) / (limit - 1)
    return [days[round(i * step)] for i in range(limit)]


def _race_one(
    series: dict[str, list[tuple[str, float]]],
    names: dict[str, str],
    days: Sequence[str],
    layout: tuple[int, int, tuple[int, int, int, int]],
    highlight: set[str],
    narrow: bool,
) -> str:
    """One layout of the race chart. Highlighted lines are coloured and (wide layout only) get
    a direct end label with a leader line; the others are light grey and live in the legend."""
    width, height, (top, right, bottom, left) = layout
    w, h = width - left - right, height - top - bottom
    vals = [v for pts in series.values() for _, v in pts] + [0.25]
    step = 0.05 if max(vals) - min(vals) > 0.12 else 0.02
    ymin = max(0.0, math.floor((min(vals) - step / 2) / step) * step)
    ymax = math.ceil((max(vals) + step / 2) / step) * step
    idx = {d: i for i, d in enumerate(days)}
    n = max(1, len(days) - 1)

    def x(d: str) -> float:
        return left + (idx[d] / n) * w if len(days) > 1 else left + w / 2

    def y(v: float) -> float:
        return top + h - ((v - ymin) / (ymax - ymin)) * h

    suffix = "n" if narrow else "w"
    cls = "race race-narrow" if narrow else "race race-wide"
    p = [
        f'<svg class="{cls}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-labelledby="race-t-{suffix} race-d-{suffix}">',
        f'<title id="race-t-{suffix}">Cumulative Brier score by forecaster</title>',
        f'<desc id="race-d-{suffix}">Running average Brier score (lower is better) after each '
        "batch day, on the questions every plotted forecaster answered. The values are also in "
        "the list and the table next to the chart.</desc>",
    ]
    t = ymin
    while t <= ymax + 1e-9:
        p.append(
            f'<line class="grid" x1="{left}" x2="{left + w}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
        )
        p.append(
            f'<text class="tick" x="{left - 6}" y="{y(t) + 4:.1f}" text-anchor="end">{t:.2f}</text>'
        )
        t = round(t + step, 10)
    yc = y(0.25)
    p.append(f'<line class="coinline" x1="{left}" x2="{left + w}" y1="{yc:.1f}" y2="{yc:.1f}"/>')
    p.append(
        f'<text class="tick coin" x="{left + w}" y="{yc - 6:.1f}" text-anchor="end">'
        "always 50% = 0.25</text>"
    )
    ticks = _day_ticks(days, 4 if narrow else 6)
    for d in ticks:
        anchor = "start" if d == ticks[0] else "end" if d == ticks[-1] else "middle"
        p.append(
            f'<text class="tick" x="{x(d):.1f}" y="{height - 10}" '
            f'text-anchor="{anchor}">{escape(d[5:])}</text>'
        )
    order = [f for f in series if f not in highlight] + [f for f in series if f in highlight]
    ends: list[list[Any]] = []
    for fid in order:
        pts = series[fid]
        if not pts:
            continue
        hot = fid in highlight
        c = series_class(fid) if hot else "s-muted"
        path = " ".join(
            f"{'M' if i == 0 else 'L'}{x(d):.1f},{y(v):.1f}" for i, (d, v) in enumerate(pts)
        )
        p.append(f'<path class="line {c}" d="{path}"/>')
        for d, v in pts:
            tip = escape(f"{names.get(fid, fid)}: {v:.3f} after {d}")
            r = 3.5 if hot else 2.5
            p.append(
                f'<g class="pt"><circle class="hit" cx="{x(d):.1f}" cy="{y(v):.1f}" r="10">'
                f"<title>{tip}</title></circle>"
                f'<circle class="dot {c}" cx="{x(d):.1f}" cy="{y(v):.1f}" r="{r}"/></g>'
            )
        if hot and not narrow:
            d_last, v_last = pts[-1]
            ends.append([y(v_last), x(d_last), fid, v_last])
    ends.sort()
    for i in range(1, len(ends)):  # at least 16 units apart, labels stay near their dots
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 16)
    for ly, lx, fid, v in ends:
        name = names.get(fid, fid)
        name = name if len(name) <= RACE_LABEL_CHARS else name[: RACE_LABEL_CHARS - 1] + "…"
        label = f"{name} {v:.3f}"
        p.append(f'<line class="leader" x1="{lx + 5:.1f}" y1="{y(series[fid][-1][1]):.1f}" '
                 f'x2="{left + w + 8}" y2="{ly:.1f}"/>')  # fmt: skip
        p.append(
            f'<text class="endlabel {series_class(fid)}" x="{left + w + 12}" y="{ly + 4:.1f}">'
            f"{escape(label)}</text>"
        )
    p.append("</svg>")
    return "".join(p)


def race_highlights(series: dict[str, list[tuple[str, float]]]) -> set[str]:
    """The lines drawn in colour: the ML model, the base rate and the best AI forecaster."""
    ai = [f for f in AI_FORECASTERS if series.get(f)]
    best = min(ai, key=lambda f: series[f][-1][1]) if ai else None
    return {f for f in HIGHLIGHT if f in series} | ({best} if best else set())


def race_svg(
    series: dict[str, list[tuple[str, float]]], names: dict[str, str], days: Sequence[str]
) -> Markup:
    """Line chart of cumulative mean Brier score per forecaster over batch days, in two
    layouts (wide, and a phone layout the CSS switches to), plus a legend sorted by the latest
    score. With fewer than `RACE_MIN_DAYS` days it shows a short note instead of a chart.

    One y-axis (Brier, lower is better), a reference at 0.25 (always saying 50%), end labels
    only for the highlighted lines, and a native tooltip on every point."""
    if len(days) < RACE_MIN_DAYS:
        return Markup(
            f'<p class="empty race-wait">The race chart appears after {RACE_MIN_DAYS} days of '
            f"results; so far there are {len(days)}. Until then the standings above and the "
            "table below show the same numbers.</p>"
        )
    hot = race_highlights(series)
    ranked = sorted((f for f in series if series[f]), key=lambda f: series[f][-1][1])
    legend = "".join(
        f'<li><span class="dot-key {series_class(f) if f in hot else "s-muted"}" '
        f'aria-hidden="true"></span><span class="lg-name">{escape(names.get(f, f))}</span> '
        f'<span class="lg-val">{series[f][-1][1]:.3f}</span></li>'
        for f in ranked
    )
    return Markup(
        '<div class="race-wrap">'
        + _race_one(series, names, days, RACE_WIDE, hot, narrow=False)
        + _race_one(series, names, days, RACE_NARROW, hot, narrow=True)
        + f'<ol class="race-legend" aria-label="Latest score, best first">{legend}</ol></div>'
    )


FOREST_W, FOREST_ROW = 680, 34
FOREST_PAD = (28, 24, 34, 170)  # top, right, bottom, left
FOREST_NARROW = (360, 40, (30, 12, 36, 118))  # phone layout: width, row height, pad
FOREST_LABEL_CHARS = 16  # longest row label on the phone layout (the tooltip has the full name)


def forest_svg(rows: Sequence[Any], names: dict[str, str]) -> Markup:
    """Forest plot: each forecaster's Brier score (dot) with its 95% day-block bootstrap
    interval (whisker), sorted best first, with the coin-flip reference at 0.25.

    Two layouts (wide, and a phone layout the CSS switches to) so the text stays readable.
    `rows` are BoardRow-like objects (forecaster_id, brier.estimate/low/high)."""
    pad = FOREST_PAD
    return Markup(
        _forest_one(rows, names, FOREST_W, FOREST_ROW, pad, narrow=False)
        + _forest_one(rows, names, *FOREST_NARROW, narrow=True)
    )


def _forest_one(
    rows: Sequence[Any],
    names: dict[str, str],
    width: int,
    row_h: int,
    pad: tuple[int, int, int, int],
    narrow: bool,
) -> str:
    rows = sorted(rows, key=lambda r: r.brier.estimate)
    top, right, bottom, left = pad
    h = top + bottom + row_h * max(1, len(rows))
    w = width - left - right
    lo = min([r.brier.low for r in rows] + [0.25])
    hi = max([r.brier.high for r in rows] + [0.25])
    step = 0.05 if hi - lo > 0.12 else 0.02
    xmin = max(0.0, math.floor((lo - step / 2) / step) * step)
    xmax = math.ceil((hi + step / 2) / step) * step

    def x(v: float) -> float:
        return left + (v - xmin) / (xmax - xmin) * w

    sfx = "-n" if narrow else "-w"
    p = [
        f'<svg class="forest {"forest-narrow" if narrow else "forest-wide"}" '
        f'viewBox="0 0 {width} {h}" role="img" aria-labelledby="forest-t{sfx} forest-d{sfx}">',
        f'<title id="forest-t{sfx}">Brier score with 95% interval per forecaster</title>',
        f'<desc id="forest-d{sfx}">Dots are mean Brier scores (lower is better); lines are 95% '
        "day-block bootstrap intervals. Overlapping intervals mean the difference is not "
        "established yet. The same numbers are in the table below.</desc>",
    ]
    t = xmin
    while t <= xmax + 1e-9:
        p.append(
            f'<line class="grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="{top - 8}" '
            f'y2="{h - bottom + 4}"/>'
        )
        p.append(
            f'<text class="tick" x="{x(t):.1f}" y="{h - 12}" text-anchor="middle">{t:.2f}</text>'
        )
        t = round(t + step, 10)
    p.append(
        f'<line class="coinline" x1="{x(0.25):.1f}" x2="{x(0.25):.1f}" y1="{top - 14}" '
        f'y2="{h - bottom + 4}"/>'
    )
    p.append(f'<text class="tick" x="{x(0.25) + 4:.1f}" y="{top - 16}">coin flip 0.25</text>')
    for i, r in enumerate(rows):
        cy = top + row_h * i + row_h / 2
        cls = series_class(r.forecaster_id)
        full = names.get(r.forecaster_id, r.forecaster_id)
        short = (
            full
            if not narrow or len(full) <= FOREST_LABEL_CHARS
            else full[: FOREST_LABEL_CHARS - 1] + "…"
        )
        name = escape(short)
        b = r.brier
        tip = escape(
            f"{names.get(r.forecaster_id, r.forecaster_id)}: {b.estimate:.3f} "
            f"(95% interval {b.low:.3f} to {b.high:.3f}, n = {r.n})"
        )
        p.append(
            f'<text class="rowlabel" x="{left - 12}" y="{cy + 4:.1f}" text-anchor="end">'
            f"{name}</text>"
        )
        p.append(
            f'<g class="pt"><title>{tip}</title>'
            f'<rect class="hit" x="{left}" y="{cy - row_h / 2:.1f}" width="{w}" '
            f'height="{row_h}"/>'
            f'<line class="whisker {cls}" x1="{x(b.low):.1f}" x2="{x(b.high):.1f}" '
            f'y1="{cy:.1f}" y2="{cy:.1f}"/>'
            f'<circle class="dot {cls}" cx="{x(b.estimate):.1f}" cy="{cy:.1f}" r="5"/></g>'
        )
    p.append("</svg>")
    return "".join(p)
