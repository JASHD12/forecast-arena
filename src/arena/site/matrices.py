"""Leaderboard matrices (T134): forecaster x topic skill heatmap and head-to-head
paired Brier differences with day-block intervals.

Colours: a diverging blue (better) / red (worse) scale around a neutral gray, three steps
per arm, derived from the dataviz reference palette's diverging pair and checked for text
contrast (every step >= 5:1 with its text colour in light and dark mode; see
docs/project/DECISIONS.md). The sign and the number are always printed in the cell, so
colour is never the only cue. Display only: verdicts stay on the boards (SPEC 10 wording rules).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from arena.scoring.core import Scored, leaderboard
from arena.scoring.stats import paired_brier_difference

MIN_N = 10
STEPS = (0.02, 0.08, 0.15)


def tone(value: float | None, better_when_positive: bool = True) -> str:
    """CSS class for a cell: hm-n (neutral), hm-b1..3 (better), hm-r1..3 (worse)."""
    if value is None or abs(value) < STEPS[0]:
        return "hm-n"
    level = 1 + sum(1 for s in STEPS[1:] if abs(value) >= s)
    good = value > 0 if better_when_positive else value < 0
    return f"hm-{'b' if good else 'r'}{level}"


def heatmap(
    scored: Sequence[Scored], fids: Sequence[str], domains: Sequence[str]
) -> dict[str, Any]:
    """Brier skill against base_rate per forecaster (rows) and topic (columns)."""
    cells: dict[str, dict[str, dict[str, Any]]] = {}
    for d in domains:
        rows = {r.forecaster_id: r for r in leaderboard([s for s in scored if s.domain == d])}
        for f in fids:
            r = rows.get(f)
            skill = None if r is None or f == "base_rate" else r.skill
            n = 0 if r is None else r.skill_n
            cells.setdefault(f, {})[d] = {
                "skill": skill,
                "n": n,
                "few": skill is not None and n < MIN_N,
                "tone": tone(skill) if skill is not None and n >= MIN_N else "hm-n",
            }
    return {"fids": [f for f in fids if f != "base_rate"], "domains": list(domains), "cells": cells}


def head_to_head(scored: Sequence[Scored], fids: Sequence[str]) -> dict[str, Any]:
    """Brier(row) - Brier(column) on the questions both answered, with a 95% interval."""
    by: dict[tuple[str, str], Scored] = {(s.forecaster_id, s.question_id): s for s in scored}
    qsets = {f: {q for g, q in by if g == f} for f in fids}
    cells: dict[str, dict[str, dict[str, Any] | None]] = {}
    for a in fids:
        for b in fids:
            if a == b:
                cells.setdefault(a, {})[b] = None
                continue
            common = sorted(qsets[a] & qsets[b])
            if len(common) < MIN_N:
                cells.setdefault(a, {})[b] = {"n": len(common), "diff": None}
                continue
            iv = paired_brier_difference(
                [by[(a, q)].batch_date for q in common],
                [by[(a, q)].probability for q in common],
                [by[(b, q)].probability for q in common],
                [by[(a, q)].outcome for q in common],
            )
            excludes = iv.low > 0 or iv.high < 0
            cells.setdefault(a, {})[b] = {
                "n": len(common), "diff": iv.estimate, "lo": iv.low, "hi": iv.high,
                "excludes_zero": excludes,
                "tone": (("hm-b2" if iv.estimate < 0 else "hm-r2") if excludes else "hm-n"),
            }  # fmt: skip
    return {"fids": list(fids), "cells": cells}
