"""The knowledge pack of "Ask the Arena" (T311): published ledger data and documents, as JSON.

The chat page runs in the visitor's browser and reads only this file. Nothing is computed here
that the site does not already show: forecasts, outcomes and boards come from the ledger and
the same board code as the leaderboard page; documents are the project's written record. Only
published data goes in (no rationales, no private data), and the size is capped (I5).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from arena.lab.docs_assistant import DOC_PATHS, Chunk, load_chunks
from arena.scoring.boards import Board
from arena.scoring.core import Record, clip, excluded
from arena.site.titles import DOMAIN_NAMES, FORECASTER_NAMES, plain_title

PACK_VERSION = 1
MAX_BYTES = 1_500_000
RECENT_BATCH_DAYS = 14
#: Lab cards read by the document search, besides the explainers and the SPEC.
LAB_GLOB = "docs/lab/*.md"
DISCLAIMER = (
    "Ask the Arena answers only from the published forecasts, results and documents of this "
    "research project. It makes no new predictions and gives no advice of any kind."
)


def _doc_paths(root: Path) -> list[str]:
    extra = sorted(str(p.relative_to(root)) for p in root.glob(LAB_GLOB))
    return [p for p in [*DOC_PATHS, *extra] if (root / p).exists()]


def _question(rec: Record, q: Any) -> dict[str, Any]:
    qid = q.question_id
    res = rec.resolutions.get(qid)
    voided = qid in rec.voids or excluded(rec, qid)
    state = "void" if voided else ("resolved" if res is not None else "open")
    outcome = res.outcome if res is not None and not voided else None
    forecasts: dict[str, list[float | None]] = {}
    for f in rec.forecasts:
        if f.question_id != qid:
            continue
        brier = None if outcome is None else round((clip(f.probability) - outcome) ** 2, 4)
        forecasts[f.forecaster_id] = [round(f.probability, 4), brier]
    return {
        "id": qid,
        "domain": q.domain,
        "template": q.template,
        "entity": q.entity,
        "title": plain_title(q),
        "text": q.text,
        "target": q.target_date.isoformat(),
        "batch": q.batch_date.isoformat(),
        "lock": q.lock_time.strftime("%Y-%m-%d %H:%M UTC"),
        "threshold": q.threshold,
        "unit": q.unit,
        "state": state,
        "outcome": outcome,
        "f": forecasts,
    }


def _board(b: Board) -> dict[str, Any]:
    return {
        "kind": b.kind,
        "domain": b.domain,
        "questions": b.questions,
        "days": b.days,
        "label": b.label,
        "rows": [
            {
                "f": r.forecaster_id,
                "n": r.n,
                "brier": round(r.brier.estimate, 4),
                "verdict": r.verdict,
            }
            for r in b.rows
        ],
    }


def build_pack(
    rec: Record,
    boards: list[Board],
    status: str,
    root: Path,
    today: date,
    recent_days: int = RECENT_BATCH_DAYS,
) -> dict[str, Any]:
    """The pack as a plain dict: recent questions with every locked forecast, boards, documents."""
    batches = sorted({q.batch_date for q in rec.questions.values()})
    keep = set(batches[-recent_days:])
    questions = [
        _question(rec, q)
        for q in sorted(rec.questions.values(), key=lambda q: (q.batch_date, q.question_id))
        if q.batch_date in keep
    ]
    chunks: list[Chunk] = load_chunks(root, _doc_paths(root))
    fids = sorted({f for q in questions for f in q["f"]})
    return {
        "version": PACK_VERSION,
        "built": today.isoformat(),
        "status": status,
        "disclaimer": DISCLAIMER,
        "forecasters": {f: FORECASTER_NAMES.get(f, f) for f in fids},
        "domains": {d: DOMAIN_NAMES.get(d, d) for d in sorted({q["domain"] for q in questions})},
        "questions": questions,
        "boards": [_board(b) for b in boards],
        "docs": [
            {"id": c.chunk_id, "path": c.path, "heading": c.heading, "text": c.text} for c in chunks
        ],
    }


def write_pack(pack: dict[str, Any], out_dir: Path) -> int:
    """Write `chat/pack.json`; refuse a pack over the size budget. Returns the byte size."""
    text = json.dumps(pack, ensure_ascii=False, separators=(",", ":"))
    size = len(text.encode("utf-8"))
    if size > MAX_BYTES:
        raise ValueError(f"chat pack is {size} bytes, over the budget of {MAX_BYTES}")
    target = out_dir / "chat"
    target.mkdir(parents=True, exist_ok=True)
    (target / "pack.json").write_text(text, encoding="utf-8")
    return size
