"""Frozen golden sets from the public ledger's live days (T380), for evaluation only.

The morning snapshots store the exact as-of context every forecaster saw, and the resolutions store
the observed outcome, so a past live question can be replayed offline with its real context. This
turns those into the golden-set format of `arena.evals.golden`. Rules: the file is frozen and
hashed before any evaluation, it is labelled "replay of live days" and never mixes with the live
score (I4), and nothing (a prompt, a threshold) may be chosen by looking at it (I8): it is a test
set, fixed in advance in a pre-registration. Voided questions and questions without a snapshot or
a resolution are left out and counted. Only the first resolution of a question counts.
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from arena.evals.golden import GoldenItem
from arena.ledger import Ledger, layout
from arena.models import Forecast, Question, Resolution

LABEL = "replay of live days"


@dataclass
class LedgerBuild:
    """The items and what was left out."""

    items: list[GoldenItem] = field(default_factory=list)
    dropped: dict[str, int] = field(default_factory=dict)

    def drop(self, why: str) -> None:
        """Count one left-out question."""
        self.dropped[why] = self.dropped.get(why, 0) + 1


def _snapshot(ledger: Ledger, domain: str, batch: date) -> dict[str, Any]:
    rel = f"{layout.snapshot_dir(domain, batch)}/morning_context.json.gz"
    if not ledger.exists(rel):
        return {}
    data: dict[str, Any] = json.loads(gzip.decompress(ledger.read_bytes(rel)))
    return data


def build_from_ledger(ledger: Ledger, topics: Sequence[str], until: date) -> LedgerBuild:
    """Golden items for every resolved question of `topics` with batch day up to `until`."""
    questions = {
        q.question_id: q for _, q in ledger.iter_family("questions") if isinstance(q, Question)
    }
    outcomes: dict[str, Resolution] = {}
    base: dict[str, float] = {}
    for _, r in ledger.iter_family("resolutions"):
        if isinstance(r, Resolution):
            outcomes.setdefault(r.question_id, r)
    for _, f in ledger.iter_family("forecasts"):
        if isinstance(f, Forecast) and f.forecaster_id == "base_rate":
            base.setdefault(f.question_id, f.probability)
    snaps: dict[tuple[str, date], dict[str, Any]] = {}
    out = LedgerBuild()
    for qid in sorted(questions):
        q = questions[qid]
        if q.domain not in topics or q.batch_date > until:
            continue
        res = outcomes.get(qid)
        if res is None:
            out.drop("no resolution (open or void)")
            continue
        key = (q.domain, q.batch_date)
        if key not in snaps:
            snaps[key] = _snapshot(ledger, q.domain, q.batch_date)
        ctx = snaps[key].get(qid)
        if not isinstance(ctx, dict):
            out.drop("no morning snapshot")
            continue
        asof = datetime.fromisoformat(str(ctx.get("asof", q.created_at.isoformat())))
        out.items.append(GoldenItem(asof.astimezone(UTC), q, ctx, int(res.outcome), base.get(qid)))
    return out


def meta(
    build: LedgerBuild, topics: Sequence[str], until: date, sha256: str, filename: str
) -> dict[str, Any]:
    """The sidecar describing a frozen file: its label, hash, scope and what was left out."""
    per_topic: dict[str, int] = {}
    for it in build.items:
        per_topic[it.question.domain] = per_topic.get(it.question.domain, 0) + 1
    return {
        "file": filename,
        "sha256": sha256,
        "label": LABEL,
        "kind": "evaluation set, never a live score (I4); never tune on it (I8)",
        "topics": sorted(topics),
        "until_batch_day": until.isoformat(),
        "items": len(build.items),
        "items_per_topic": dict(sorted(per_topic.items())),
        "dropped": dict(sorted(build.dropped.items())),
    }
