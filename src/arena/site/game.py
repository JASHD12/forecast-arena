"""Data for the "Can you beat the AI?" game (T130).

Two decks:

- `live`: resolved questions of the live record, with every forecaster's probability as
  published before the answer existed.
- `practice`: past days from the frozen evaluation set (evals/golden), against the
  benchmark base rate only. Labelled practice everywhere: not part of any record or score.

Players' answers stay in the browser's memory for the visit; nothing is stored or sent.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from arena.scoring.core import Record, excluded
from arena.site.titles import domain_name, plain_title

PRACTICE_ITEMS = 60
SERIES_DAYS = 7


def live_deck(rec: Record) -> list[dict[str, Any]]:
    """Resolved, scored questions with each forecaster's published probability."""
    by_q: dict[str, dict[str, float]] = {}
    for s in rec.scored:
        by_q.setdefault(s.question_id, {})[s.forecaster_id] = round(s.probability, 4)
    out = []
    for qid, fs in sorted(by_q.items()):
        q = rec.questions[qid]
        if excluded(rec, qid) or qid not in rec.resolutions:
            continue
        out.append({
            "id": qid, "title": plain_title(q), "topic": domain_name(q.domain),
            "rule": q.resolution_rule, "outcome": rec.resolutions[qid].outcome,
            "forecasts": fs, "url": f"questions/{qid}.html",
        })  # fmt: skip
    return out


def practice_deck(golden: Path | None, n: int = PRACTICE_ITEMS) -> list[dict[str, Any]]:
    """A seeded sample of the golden set with the last days of the asked statistic."""
    if golden is None or not golden.exists():
        return []
    from arena.evals.golden import load
    from arena.evals.run import sample

    items, _ = load(golden)
    out = []
    for it in sample(items, n):
        q = it.question
        stat = str(q.params.get("stat", ""))
        thr = q.params.get("reference_mean") if q.template == "up_vs_today" else q.threshold
        series = [{"day": r["day"], "value": r.get(stat)} for r in it.context.get("daily", [])]
        out.append({
            "id": q.question_id, "title": plain_title(q), "topic": domain_name(q.domain),
            "rule": q.resolution_rule, "outcome": it.outcome,
            "forecasts": {} if it.base_rate is None else {"base_rate": round(it.base_rate, 4)},
            "series": series[-SERIES_DAYS:], "threshold": thr, "unit": q.unit,
        })  # fmt: skip
    random.Random(0).shuffle(out)
    return out
