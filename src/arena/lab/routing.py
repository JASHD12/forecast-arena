"""Cost routing over stored forecasts (T250, `lab/prereg/routing.md`).

A cascade answers with a cheap forecast when it is confident and escalates to the paid model
otherwise. Everything is computed offline from forecasts that already exist for the same 276
frozen test questions: the `ml` backtest, the open fine-tuned model, Claude's `llm_context` and
the base rate. The saving is the share of paid calls a rule would not have made.

Rules (the first is the pre-registered primary rule, fixed before the Claude answers existed):
- `pair`:    answer with the mean of `ml` and `ft` when both are decisive (|p - 0.5| >= delta)
             and agree (|ml - ft| <= gamma); otherwise escalate. delta = 0.15, gamma = 0.10.
- `ml_only`: answer with `ml` when it is decisive (|ml - 0.5| >= delta); otherwise escalate.
The grid over delta is descriptive.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from arena.scoring import stats

PRIMARY_DELTA = 0.15
GAMMA = 0.10
DELTAS = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30)


@dataclass(frozen=True)
class Item:
    """One test question with every stored forecast for it."""

    id: str
    day: str
    outcome: int
    ml: float
    ft: float
    claude: float
    base: float


def decide(it: Item, rule: str, delta: float, gamma: float = GAMMA) -> tuple[float, bool]:
    """(probability, escalated) for one item under a rule."""
    if rule == "pair":
        cheap = (
            abs(it.ml - 0.5) >= delta and abs(it.ft - 0.5) >= delta and abs(it.ml - it.ft) <= gamma
        )
        return ((it.ml + it.ft) / 2, False) if cheap else (it.claude, True)
    if rule == "ml_only":
        return (it.ml, False) if abs(it.ml - 0.5) >= delta else (it.claude, True)
    raise ValueError(f"unknown rule {rule!r}")


def _brier(p: Sequence[float], y: Sequence[int]) -> float:
    return round(float(np.mean(stats.brier_terms(list(p), list(y)))), 4)


def study(rows: Sequence[Item]) -> dict[str, Any]:
    """Arms, the delta grid for both rules and paired differences for the primary rule."""
    y = [r.outcome for r in rows]
    days = [r.day for r in rows]
    arms: dict[str, dict[str, float | int | str | None]] = {}
    for name, p in (
        ("claude (llm_context)", [r.claude for r in rows]),
        ("ml", [r.ml for r in rows]),
        ("ft (open fine-tuned model)", [r.ft for r in rows]),
        ("base_rate", [r.base for r in rows]),
    ):
        arms[name] = {
            "n": len(rows),
            "brier": _brier(p, y),
            "paid_calls": len(rows) if name.startswith("claude") else 0,
        }
    curve: list[dict[str, float | int | str | None]] = []
    chosen: dict[str, list[float]] = {}
    for rule in ("pair", "ml_only"):
        for d in DELTAS:
            dec = [decide(r, rule, d) for r in rows]
            p = [x[0] for x in dec]
            esc = sum(x[1] for x in dec)
            curve.append(
                {
                    "rule": rule,
                    "delta": d,
                    "gamma": GAMMA if rule == "pair" else None,
                    "n": len(rows),
                    "escalated": esc,
                    "paid_calls_avoided": len(rows) - esc,
                    "avoided_pct": round(100 * (len(rows) - esc) / len(rows), 1),
                    "brier": _brier(p, y),
                }
            )
            if rule == "pair" and d == PRIMARY_DELTA:
                chosen["primary"] = p
                arms["router (primary: pair, delta 0.15, gamma 0.10)"] = {
                    "n": len(rows),
                    "brier": _brier(p, y),
                    "paid_calls": esc,
                }
    paired: list[dict[str, Any]] = []
    primary = chosen["primary"]
    for name, other in (
        ("claude (llm_context)", [r.claude for r in rows]),
        ("ml", [r.ml for r in rows]),
        ("base_rate", [r.base for r in rows]),
    ):
        iv = stats.paired_brier_difference(days, primary, other, y)
        paired.append(
            {
                "a": "router (primary)",
                "b": name,
                "split": "test_all",
                "diff": iv.estimate,
                "lo": iv.low,
                "hi": iv.high,
                "n": len(rows),
                "days": len(set(days)),
            }
        )
    base_calls = len(rows)
    router_calls = int(arms["router (primary: pair, delta 0.15, gamma 0.10)"]["paid_calls"] or 0)
    notes = [
        f"{len(rows)} questions with every forecast available; the primary rule escalates "
        f"{router_calls} of {base_calls} ({100 * router_calls / base_calls:.1f}%) to the paid "
        "model.",
        "The cheap pair is the `ml` backtest and the open fine-tuned GGUF model with its pinned "
        "calibration; the paid arm is `llm_context` (Claude Haiku).",
    ]
    return {"arms": arms, "curve": curve, "paired": paired, "notes": notes}
