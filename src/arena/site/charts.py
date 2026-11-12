"""Inline SVG charts (no JavaScript). Colours come from CSS variables, so both themes work;
every chart has a <title>/<desc>, native tooltips on marks, and a data table next to it."""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

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
