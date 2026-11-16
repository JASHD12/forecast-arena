"""Display-only participation evidence; never changes statistical populations."""

from __future__ import annotations

from typing import Any

from arena.scoring.core import Record


def participants(rec: Record) -> list[dict[str, Any]]:
    """Include published, skipped and unresolved forecasters without inventing scores."""
    ids = sorted({f.forecaster_id for f in rec.forecasts} | {s.forecaster_id for s in rec.skips})
    result = []
    for fid in ids:
        fs = [f for f in rec.forecasts if f.forecaster_id == fid]
        scored = sum(s.forecaster_id == fid for s in rec.scored)
        skipped = [s for s in rec.skips if s.forecaster_id == fid]
        result.append(
            {
                "id": fid,
                "published": len(fs),
                "scored": scored,
                "pending": sum(f.question_id not in rec.resolutions for f in fs),
                "sampled_out": sum(s.reason_code == "not_sampled" for s in skipped),
                "failed": sum(s.reason_code != "not_sampled" for s in skipped),
            }
        )
    return result


def sample_links(rec: Record, question: Any) -> list[Any]:
    """Actual graph samples in the same domain and batch, never substitute forecasts."""
    return [
        rec.questions[f.question_id]
        for f in rec.forecasts
        if f.forecaster_id == "agent_graph"
        and f.question_id in rec.questions
        and rec.questions[f.question_id].domain == question.domain
        and rec.questions[f.question_id].batch_date == question.batch_date
    ]
