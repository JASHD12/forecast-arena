"""The README's standings: a JSON snapshot of the scored record and a forest plot (T390).

The ledger lives on its own branch, so the README cannot read it in CI.
`scripts/standings_snapshot.py` reads a ledger checkout by hand (like `scripts/screenshots.py`) and
writes `docs/data/standings.json` and `docs/img/standings.svg`; `scripts/readme_sections.py` then
builds the README's result lines from that committed JSON and the committed lab results, so no
number in the README is typed by hand (I5).

Boards follow `arena.scoring.boards`: the common set of questions all four headline forecasters
answered, 95% day-block intervals, the label "too early to tell" under the SPEC 10 thresholds.
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from datetime import date
from typing import Any

from arena.forecasters.catalog import FORECASTER_NAMES
from arena.scoring.boards import COMMON_GROUP, Board, all_boards, official, settling_rule
from arena.scoring.core import Scored

TOPICS = ("power", "weather", "attention", "markets", "crypto")
#: Series colours of the four headline forecasters (the light values of `site/static/style.css`).
COLOURS = {"ml": "#2a78d6", "llm_context": "#1baf7a", "agent": "#6250d6", "base_rate": "#7b818c"}


def _rows(b: Board) -> list[dict[str, Any]]:
    out = []
    for r in b.rows:
        vs = r.vs_reference
        out.append(
            {
                "id": r.forecaster_id,
                "name": FORECASTER_NAMES.get(r.forecaster_id, r.forecaster_id),
                "n": r.n,
                "brier": round(r.brier.estimate, 4),
                "lo": round(r.brier.low, 4),
                "hi": round(r.brier.high, 4),
                "vs_base": None
                if vs is None
                else {
                    "diff": round(vs.estimate, 4),
                    "lo": round(vs.low, 4),
                    "hi": round(vs.high, 4),
                },
            }
        )
    return out


def _board(b: Board) -> dict[str, Any]:
    return {"label": b.label, "questions": b.questions, "days": b.days, "rows": _rows(b)}


def build_snapshot(scored: Sequence[Scored], start: date | None, today: date) -> dict[str, Any]:
    """Boards of the official record and, per topic, of all days (rehearsal included)."""
    off = official(scored, start)
    off_days = len({s.batch_date for s in off})
    domains = sorted({s.domain for s in scored})
    settling = settling_rule(scored, start)
    headline = [b for b in all_boards(off, domains, off_days, settling) if b.kind == "common"]
    every = [b for b in all_boards(scored, domains) if b.kind == "common"]
    return {
        "generated_on": today.isoformat(),
        "official_start": None if start is None else start.isoformat(),
        "official_days": off_days,
        "group": list(COMMON_GROUP),
        "official": next(_board(b) for b in headline if b.domain == "overall"),
        "topics_official": {b.domain: _board(b) for b in headline if b.domain != "overall"},
        "topics_all_days": {b.domain: _board(b) for b in every if b.domain != "overall"},
    }


def render_svg(snap: dict[str, Any]) -> str:
    """A forest plot of the official common-set Brier scores (lower is better)."""
    board = snap["official"]
    rows = board["rows"]
    w, left, right, top, row_h = 640, 190, 90, 56, 38
    h = top + row_h * max(1, len(rows)) + 62
    vals = [v for r in rows for v in (r["lo"], r["hi"])] or [0.0, 0.3]
    lo, hi = max(0.0, min(vals) - 0.02), max(vals) + 0.02
    plot = w - left - right

    def x(v: float) -> float:
        return left + (v - lo) / (hi - lo) * plot

    e = html.escape
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        'role="img" aria-labelledby="t d" font-family="system-ui, sans-serif">',
        '<title id="t">Official standings of the four headline forecasters</title>',
        f'<desc id="d">Brier score with a 95 percent interval for each forecaster on '
        f"{board['questions']} questions over {snap['official_days']} official days; "
        "lower is better."
        f"{' Label: ' + e(board['label']) + '.' if board['label'] else ''}</desc>",
        f'<rect width="{w}" height="{h}" rx="10" fill="#ffffff" stroke="#d5d9e2"/>',
        f'<text x="{left}" y="26" font-size="15" font-weight="600" fill="#141a26">'
        "Who is ahead? Brier score, lower is better</text>",
    ]
    base = next((r for r in rows if r["id"] == "base_rate"), None)
    if base is not None:
        bx = x(base["brier"])
        out.append(
            f'<line x1="{bx:.1f}" y1="{top - 10}" x2="{bx:.1f}" y2="{top + row_h * len(rows)}" '
            'stroke="#7b818c" stroke-dasharray="4 4"/>'
        )
        out.append(
            f'<text x="{bx:.1f}" y="{top - 14}" font-size="11" text-anchor="middle" fill="#545e70">'
            "base rate</text>"
        )
    for i, r in enumerate(rows):
        y = top + row_h * i + row_h / 2
        c = COLOURS.get(r["id"], "#34495e")
        out += [
            f'<text x="{left - 12}" y="{y + 4:.1f}" font-size="13" text-anchor="end" '
            'fill="#141a26">'
            f"{e(r['name'])}</text>",
            f'<line x1="{x(r["lo"]):.1f}" y1="{y:.1f}" x2="{x(r["hi"]):.1f}" y2="{y:.1f}" '
            f'stroke="{c}" stroke-width="3"/>',
            f'<circle cx="{x(r["brier"]):.1f}" cy="{y:.1f}" r="6" fill="{c}"/>',
            f'<text x="{w - right + 10}" y="{y + 4:.1f}" font-size="12" fill="#141a26">'
            f"{r['brier']:.3f}</text>",
        ]
    foot = (
        f"{board['questions']} questions, {snap['official_days']} official days "
        f"since {snap['official_start']}"
    )
    out.append(f'<text x="{left}" y="{h - 34}" font-size="12" fill="#545e70">{e(foot)}</text>')
    label = board["label"] or "interval = 95% day-block bootstrap"
    out.append(
        f'<text x="{left}" y="{h - 14}" font-size="13" font-weight="600" fill="#b45309">'
        f"{e(label)}</text>"
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"
