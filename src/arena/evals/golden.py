"""The golden set: past questions with the as-of context they would have had and their
outcome, generated and resolved by the production domain code (SPEC 8.1 replay).

Each item records the morning `asof`, the question, the context the live forecasters
would have seen at that time, the outcome, and the benchmark's `base_rate` probability
(from replayed history before that morning only). The file is frozen once written: its
SHA-256 goes into every result, so results on different sets are never compared.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from arena.domains.base import Domain
from arena.forecasters.baselines import BaseRate
from arena.forecasters.replay import REPLAY_MORNING, ReplayHistory
from arena.models import Forecast, Question, Resolution, canonical_json, parse_record


@dataclass(frozen=True)
class GoldenItem:
    """One evaluation question."""

    asof: datetime
    question: Question
    context: dict[str, Any]
    outcome: int
    base_rate: float | None


def build(domain: Domain, first: date, last: date, resolve_at: datetime) -> list[GoldenItem]:
    """Items for every batch day from `first` to `last` that resolved by `resolve_at`."""
    base = BaseRate(ReplayHistory(domain))
    out = []
    d = first
    while d <= last:
        asof = datetime.combine(d, REPLAY_MORNING, tzinfo=UTC)
        for q in domain.generate_questions(d, asof):
            r = domain.resolve(q, resolve_at)
            if not isinstance(r, Resolution):
                continue
            ctx = domain.context(q, asof)
            b = base.forecast(q, ctx, asof)
            p = b.probability if isinstance(b, Forecast) else None
            out.append(GoldenItem(asof, q, ctx, r.outcome, p))
        d += timedelta(days=1)
    return out


def dump(items: list[GoldenItem], path: Path) -> str:
    """Write the set as JSON Lines; returns its SHA-256."""
    lines = []
    for it in items:
        lines.append(json.dumps({"asof": it.asof.isoformat(),
                                 "question": json.loads(canonical_json(it.question)),
                                 "context": it.context, "outcome": it.outcome,
                                 "base_rate": it.base_rate}, sort_keys=True))  # fmt: skip
    body = ("\n".join(lines) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return hashlib.sha256(body).hexdigest()


def load(path: Path) -> tuple[list[GoldenItem], str]:
    """Read a golden set and its SHA-256."""
    body = path.read_bytes()
    items = []
    for line in body.decode().splitlines():
        if not line.strip():
            continue
        x = json.loads(line)
        q = parse_record(json.dumps(x["question"]))
        assert isinstance(q, Question)
        items.append(GoldenItem(datetime.fromisoformat(x["asof"]), q, x["context"],
                                int(x["outcome"]), x["base_rate"]))  # fmt: skip
    return items, hashlib.sha256(body).hexdigest()
