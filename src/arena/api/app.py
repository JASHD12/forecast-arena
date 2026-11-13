"""`arena api`: a read-only REST API over a snapshot of the ledger (T150, FastAPI).

Same data and models as the static JSON API (`site/api.py`), but queryable: filter
questions, fetch one question, get the leaderboard for a topic, or run one read-only SQL
SELECT (DuckDB with external access switched off, as in `arena mcp`). OpenAPI docs are
served at /docs. The snapshot is loaded at start-up; nothing can write to the ledger.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from arena.ledger import Ledger
from arena.ledger.layout import OFFICIAL_START_PATH
from arena.mcp_server import Benchmark, SqlRefused
from arena.scoring.boards import board, official
from arena.site.api import LeaderboardFile, LeaderboardRow, QuestionOut, _question
from arena.site.build import question_href


class Health(BaseModel):
    """Liveness and snapshot size."""

    status: Literal["ok"] = "ok"
    questions: int
    forecasts: int


class SqlResult(BaseModel):
    """Result of one read-only query."""

    columns: list[str]
    rows: list[list[Any]]
    truncated: bool


def create_app(ledger: Ledger) -> FastAPI:
    """The API over a snapshot of `ledger` taken now."""
    import json

    from arena.clock import SystemClock

    b = Benchmark(ledger)
    rec = b.rec
    start = None
    if ledger.exists(OFFICIAL_START_PATH):
        start = date.fromisoformat(
            json.loads(ledger.read_bytes(OFFICIAL_START_PATH))["official_start"]
        )
    app = FastAPI(title="Forecast Arena API", version="1",
                  description="Read-only access to the Forecast Arena record. A research "
                  "project, not advice.")  # fmt: skip

    @app.get("/health", response_model=Health)
    def health() -> Health:
        return Health(questions=len(rec.questions), forecasts=len(rec.forecasts))

    @app.get("/questions", response_model=list[QuestionOut])
    def questions(
        domain: str | None = None,
        status: Literal["open", "resolved", "void", "all"] = "all",
        limit: int = Query(50, ge=1, le=500),
    ) -> list[QuestionOut]:
        qs = sorted(rec.questions.values(), key=lambda q: (q.batch_date, q.question_id),
                    reverse=True)  # fmt: skip
        out = []
        for q in qs:
            if domain is not None and q.domain != domain:
                continue
            item = _question(rec, q.question_id, question_href(q.question_id))
            if status == "all" or item.status == status:
                out.append(item)
            if len(out) >= limit:
                break
        return out

    @app.get("/questions/{question_id}", response_model=QuestionOut)
    def question(question_id: str) -> QuestionOut:
        if question_id not in rec.questions:
            raise HTTPException(status_code=404, detail="unknown question")
        return _question(rec, question_id, question_href(question_id))

    @app.get("/leaderboard", response_model=LeaderboardFile)
    def leaderboard(domain: str = "overall") -> LeaderboardFile:
        scored = official(rec.scored, start) if start else rec.scored
        days = len({s.batch_date for s in scored}) if start else None
        bd = board(scored, "all", domain, days)
        rows = [LeaderboardRow(forecaster_id=r.forecaster_id, n=r.n, brier=r.brier.estimate,
                               brier_low=r.brier.low, brier_high=r.brier.high, log_score=r.log,
                               brier_minus_base_rate=None if r.vs_reference is None
                               else r.vs_reference.estimate) for r in bd.rows]  # fmt: skip
        return LeaderboardFile(generated_at=SystemClock().now(),
                               scope="official" if start else "rehearsal", label=bd.label,
                               questions=bd.questions, days=bd.days, rows=rows)  # fmt: skip

    @app.get("/sql", response_model=SqlResult)
    def sql(q: str = Query(..., description="One SELECT over questions, forecasts, "
                                           "resolutions, skips")) -> SqlResult:  # fmt: skip
        try:
            return SqlResult(**b.run_sql(q))
        except SqlRefused as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # DuckDB errors: bad SQL, blocked file access
            raise HTTPException(status_code=400, detail=f"query failed: {exc}"[:300]) from exc

    return app
