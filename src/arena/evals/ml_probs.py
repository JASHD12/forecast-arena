"""Replayed `ml` probabilities for a frozen golden set (T380).

`agent_analyst` starts from the `ml` forecast, so an offline evaluation needs the probability the
production `ml` model would have given each golden question that morning. It comes from the same
walk-forward backtest that produced the model card: each batch day sees only data known before
it, the model is retrained on an expanding window, and the questions and their ids are made by
the production domain code. This is a **replay** (I4), not a live forecast, and it never enters a
live score. The file names the golden set it belongs to and that set's SHA-256.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from arena.evals.golden import load


class ReplayError(Exception):
    """The replay does not cover the golden set."""


class _Record(Protocol):
    question_id: str
    forecaster_id: str
    probability: float


def batch_range(golden: Path) -> tuple[date, date]:
    """First and last batch day of the golden set's questions."""
    items, _ = load(golden)
    days = [it.question.batch_date for it in items]
    if not days:
        raise ReplayError(f"{golden} has no items")
    return min(days), max(days)


def build_payload(golden: Path, records: Iterable[_Record], note: str) -> dict[str, Any]:
    """The ml-probs file content: one `ml` probability per golden question, none missing."""
    items, sha = load(golden)
    wanted = {it.question.question_id for it in items}
    probs = {
        r.question_id: round(float(r.probability), 6)
        for r in records
        if r.forecaster_id == "ml" and r.question_id in wanted
    }
    missing = sorted(wanted - set(probs))
    if missing:
        raise ReplayError(
            f"{len(missing)} golden questions have no replayed ml probability, e.g. {missing[0]}"
        )
    return {
        "golden": golden.name,
        "golden_sha256": sha,
        "kind": "replay",
        "note": note,
        "probabilities": dict(sorted(probs.items())),
    }


def write(payload: dict[str, Any], out: Path) -> None:
    """Write the file with sorted keys and a final newline."""
    out.write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n", encoding="utf-8")
