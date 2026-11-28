"""Selection of the `quant-r2` reference estimate on the October set, and its one-time check (T399).

Pre-registered in `lab/prereg/agent-quant-r2.md`. The design was chosen on the 186 October items
(`power-2026-10.jsonl`) only; the 90 November items are used once, as the confirmatory comparison
of the r2 estimate with the r1 estimate (H-Q5). No model call is made: every number here comes from
the stored contexts and outcomes. The r1 estimate is kept below as a frozen reference copy so the
comparison stays reproducible after `agent/quant.py` moved on.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from itertools import pairwise
from typing import Any

from arena.agent.quant import ESTIMATE_CLIP, MIN_HISTORY_DAYS, power_estimate
from arena.agent.tools import normal_probability
from arena.evals.golden import GoldenItem
from arena.models import Question
from arena.scoring.stats import paired_brier_difference

R1_RECENT_DAYS = 7


def _hit(value: float, comparator: str, threshold: float) -> bool:
    if comparator == "gt":
        return value > threshold
    if comparator == "ge":
        return value >= threshold
    return value < threshold


def r1_estimate(q: Question, ctx: Mapping[str, Any]) -> float:
    """The r1 estimate, frozen: mean of window share, last-7-days share and "latest day crossed"."""
    stat = str(q.params.get("stat", ""))
    threshold = float(q.params["reference_mean"]) if q.template == "up_vs_today" else q.threshold
    daily = [d for d in ctx.get("daily", []) if stat in d]
    if threshold is None or len(daily) < MIN_HISTORY_DAYS:
        raise ValueError("not enough stored history for a reference estimate")
    hits = [_hit(float(d[stat]), q.comparator, float(threshold)) for d in daily]
    recent = hits[-R1_RECENT_DAYS:]
    p = (sum(hits) / len(hits) + sum(recent) / len(recent) + (1.0 if hits[-1] else 0.0)) / 3
    return min(ESTIMATE_CLIP[1], max(ESTIMATE_CLIP[0], p))


def _series(q: Question, ctx: Mapping[str, Any]) -> tuple[list[date], list[float]]:
    stat = str(q.params.get("stat", ""))
    rows = [d for d in ctx["daily"] if stat in d]
    return [date.fromisoformat(d["day"]) for d in rows], [float(d[stat]) for d in rows]


def _clip(p: float) -> float:
    return min(ESTIMATE_CLIP[1], max(ESTIMATE_CLIP[0], p))


def _persistence(q: Question, ctx: Mapping[str, Any], *, weekday: bool = False) -> float:
    days, values = _series(q, ctx)
    diffs = [b - a for a, b in pairwise(values)]
    ahead = max(1, (q.target_date - days[-1]).days)
    sd = max(statistics.pstdev(diffs), 1e-6) * math.sqrt(ahead)
    centre = values[-1]
    if weekday:
        same = [
            v for v, d in zip(values, days, strict=True) if d.weekday() == q.target_date.weekday()
        ]
        centre = 0.5 * values[-1] + 0.5 * statistics.mean(same) if same else values[-1]
    direction = "lt" if q.comparator == "lt" else "gt"
    return _clip(normal_probability(centre, sd, float(q.threshold or 0.0), direction))


def _up_changes(q: Question, ctx: Mapping[str, Any]) -> tuple[list[float], list[float]]:
    days, values = _series(q, ctx)
    diffs = [b - a for a, b in pairwise(values)]
    same = [
        d
        for day, d in zip(days[1:], diffs, strict=True)
        if day.weekday() == q.target_date.weekday()
    ]
    return diffs, same


def _up_weekday(q: Question, ctx: Mapping[str, Any]) -> float:
    diffs, same = _up_changes(q, ctx)
    return _clip(
        normal_probability(
            statistics.mean(same) if same else 0.0, statistics.pstdev(diffs), 0.0, "gt"
        )
    )


def _up_share(q: Question, ctx: Mapping[str, Any]) -> float:
    diffs, _ = _up_changes(q, ctx)
    return sum(1 for d in diffs if d > 0) / len(diffs)


CANDIDATES_THRESHOLD: dict[str, Callable[[Question, Mapping[str, Any]], float]] = {
    "r1 estimate": r1_estimate,
    "persistence, normal error (r2)": lambda q, c: _persistence(q, c),
    "weekday-adjusted persistence": lambda q, c: _persistence(q, c, weekday=True),
    "blend of r1 and persistence": lambda q, c: _clip(
        0.5 * r1_estimate(q, c) + 0.5 * _persistence(q, c)
    ),
}
CANDIDATES_UP: dict[str, Callable[[Question, Mapping[str, Any]], float]] = {
    "r1 estimate": r1_estimate,
    "always 0.5": lambda q, c: 0.5,
    "same-weekday change, normal tail (r2)": _up_weekday,
    "share of up days": _up_share,
}


def r2_estimate(q: Question, ctx: Mapping[str, Any]) -> float:
    """The estimate `agent_quant` r2 actually serves (the tool result's probability)."""
    return float(power_estimate(q, ctx)["probability"])


def _brier(pairs: Sequence[tuple[float, int]]) -> float:
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def selection(items: Sequence[GoldenItem]) -> dict[str, dict[str, float]]:
    """Brier per candidate and template on `items` (the October set), plus an 'all' column."""
    by: dict[str, dict[str, list[tuple[float, int]]]] = defaultdict(lambda: defaultdict(list))
    for it in items:
        q = it.question
        cands = CANDIDATES_UP if q.template == "up_vs_today" else CANDIDATES_THRESHOLD
        for name, fn in cands.items():
            by[q.template][name].append((fn(q, it.context), it.outcome))
    out: dict[str, dict[str, float]] = {}
    for template, per in by.items():
        out[template] = {name: _brier(pairs) for name, pairs in per.items()}
    return out


def confirmation(items: Sequence[GoldenItem]) -> dict[str, Any]:
    """H-Q5 on `items` (the November set, once): r2 estimate against the r1 estimate."""
    days, p2, p1, ys = [], [], [], []
    per: dict[str, list[tuple[float, float, int]]] = defaultdict(list)
    for it in items:
        q = it.question
        a, b = r2_estimate(q, it.context), r1_estimate(q, it.context)
        days.append(q.batch_date)
        p2.append(a)
        p1.append(b)
        ys.append(it.outcome)
        per[q.template].append((a, b, it.outcome))
    diff = paired_brier_difference(days, p2, p1, ys)
    return {
        "n": len(ys),
        "brier_r2": _brier(list(zip(p2, ys, strict=True))),
        "brier_r1": _brier(list(zip(p1, ys, strict=True))),
        "diff": diff,
        "per_template": {
            t: (_brier([(a, y) for a, _, y in rows]), _brier([(b, y) for _, b, y in rows]))
            for t, rows in sorted(per.items())
        },
    }
