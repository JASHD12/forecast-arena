"""Replay of the Hedge forecaster on the live record (T293).

Walk forward over batch days: on each day the model is trained on resolved forecasts of days at
least `LAG_DAYS` earlier only, then answers every question of that day that at least two experts
answered. Compared on identical questions: the Hedge blend, the equal-weight mean of the experts,
Thompson sampling (pick one expert per question), each single expert, and, as an unreachable
reference, the best single expert in hindsight. Paired day-block intervals against the equal-weight
mean and against `ml`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, time
from typing import Any

import numpy as np

from arena.forecasters import bandit as bd
from arena.scoring import stats
from arena.scoring.core import Scored


def replay(scored: Sequence[Scored], min_experts: int = 2) -> dict[str, Any]:
    """Probabilities of every arm per question (identical question set) plus labels and days."""
    by_q: dict[str, dict[str, Scored]] = defaultdict(dict)
    for s in scored:
        if s.forecaster_id in bd.EXPERTS:
            by_q[s.question_id][s.forecaster_id] = s
    days = sorted({next(iter(c.values())).batch_date for c in by_q.values()})
    arms: dict[str, list[float]] = defaultdict(list)
    day_of: list[Any] = []
    outcome: list[int] = []
    ids: list[str] = []
    for day in days:
        asof = datetime.combine(day, time(7), tzinfo=UTC)
        model = bd.train(scored, asof)
        for qid, cell in sorted(by_q.items()):
            first = next(iter(cell.values()))
            if first.batch_date != day or len(cell) < min_experts:
                continue
            peers = {e: s.probability for e, s in cell.items()}
            p, _ = model.predict(first.domain, peers)
            pick = bd.thompson_pick(first.domain, scored, asof, qid, tuple(peers))
            arms["hedge"].append(p)
            arms["equal_mean"].append(sum(peers.values()) / len(peers))
            arms["thompson"].append(peers[pick])
            for e in bd.EXPERTS:
                arms[e].append(peers.get(e, float("nan")))
            day_of.append(day.isoformat())
            outcome.append(first.outcome)
            ids.append(qid)
    return {"arms": dict(arms), "days": day_of, "y": outcome, "ids": ids}


def summarise(
    rep: dict[str, Any],
) -> tuple[dict[str, dict[str, float | int]], list[dict[str, Any]]]:
    """Brier per arm on the questions every compared arm answered, and paired differences."""
    y = np.asarray(rep["y"])
    arms = {k: np.asarray(v, float) for k, v in rep["arms"].items()}
    core = [k for k in ("hedge", "equal_mean", "thompson") if k in arms]
    ok = np.ones(len(y), bool)
    for k in [*core, "ml"]:
        if k in arms:
            ok &= ~np.isnan(arms[k])
    metrics: dict[str, dict[str, float | int]] = {}
    for k, v in arms.items():
        m = ok & ~np.isnan(v)
        if m.sum():
            metrics[k] = {
                "n": int(m.sum()),
                "brier": round(float(np.mean(stats.brier_terms(v[m].tolist(), y[m].tolist()))), 4),
            }
    own = {k: v for k, v in metrics.items() if k in bd.EXPERTS}
    if own:
        best = min(own, key=lambda k: own[k]["brier"])
        metrics["best_expert_in_hindsight"] = dict(own[best])
    days = np.asarray(rep["days"])
    paired = []
    for a, b in (("hedge", "equal_mean"), ("hedge", "ml"), ("hedge", "thompson")):
        if a in arms and b in arms:
            m = ok & ~np.isnan(arms[a]) & ~np.isnan(arms[b])
            if m.sum() >= 10:
                iv = stats.paired_brier_difference(
                    list(days[m]), arms[a][m].tolist(), arms[b][m].tolist(), y[m].tolist()
                )
                paired.append(
                    {
                        "a": a,
                        "b": b,
                        "diff": iv.estimate,
                        "lo": iv.low,
                        "hi": iv.high,
                        "n": iv.n,
                        "days": iv.days,
                    }
                )
    return metrics, paired
