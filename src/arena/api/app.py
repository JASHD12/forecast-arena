"""`arena api`: a read-only REST API over a snapshot of the ledger (T150, FastAPI).

Same data and models as the static JSON API (`site/api.py`), but queryable: filter
questions, fetch one question, get the leaderboard for a topic, or run one read-only SQL
SELECT (DuckDB with external access switched off, as in `arena mcp`). OpenAPI docs are
served at /docs. The snapshot is loaded at start-up; nothing can write to the ledger.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from arena.api.metrics import ApiMetrics, install
from arena.ledger import Ledger
from arena.ledger.layout import OFFICIAL_START_PATH
from arena.mcp_server import Benchmark, SqlRefused
from arena.scoring.boards import board, official, settling_rule
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


class PowerRequest(BaseModel):
    """One electricity question: the as-of daily rows plus the threshold to test."""

    stat: Literal["mean", "max", "min", "spread", "evening"]
    target_date: date
    daily: list[dict[str, Any]]
    threshold: float
    comparator: Literal["gt", "lt"] = "gt"


class PowerPrediction(BaseModel):
    """Calibrated probability and the quantiles behind it."""

    probability: float
    raw: float
    quantiles: dict[str, float]
    version: str


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
    app = FastAPI(
        title="Forecast Arena API",
        version="1",
        description="Read-only access to the Forecast Arena record. A research "
        "project, not advice.",
    )

    metrics = ApiMetrics()
    metrics.questions.set(len(rec.questions))
    metrics.forecasts.set(len(rec.forecasts))
    install(app, metrics)

    @app.get("/health", response_model=Health)
    def health() -> Health:
        return Health(questions=len(rec.questions), forecasts=len(rec.forecasts))

    @app.get("/questions", response_model=list[QuestionOut])
    def questions(
        domain: str | None = None,
        status: Literal["open", "resolved", "void", "all"] = "all",
        limit: int = Query(50, ge=1, le=500),
    ) -> list[QuestionOut]:
        qs = sorted(
            rec.questions.values(), key=lambda q: (q.batch_date, q.question_id), reverse=True
        )
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
        bd = board(scored, "all", domain, days, settling_rule(rec.scored, start))
        rows = [
            LeaderboardRow(
                forecaster_id=r.forecaster_id,
                n=r.n,
                brier=r.brier.estimate,
                brier_low=r.brier.low,
                brier_high=r.brier.high,
                log_score=r.log,
                brier_minus_base_rate=None if r.vs_reference is None else r.vs_reference.estimate,
            )
            for r in bd.rows
        ]
        return LeaderboardFile(
            generated_at=SystemClock().now(),
            scope="official" if start else "rehearsal",
            label=bd.label,
            questions=bd.questions,
            days=bd.days,
            rows=rows,
        )

    @app.get("/sql", response_model=SqlResult)
    def sql(
        q: str = Query(..., description="One SELECT over questions, forecasts, resolutions, skips"),
    ) -> SqlResult:
        try:
            return SqlResult(**b.run_sql(q))
        except SqlRefused as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # DuckDB errors: bad SQL, blocked file access
            raise HTTPException(status_code=400, detail=f"query failed: {exc}"[:300]) from exc

    power_model: Any = None
    onnx_dir = os.environ.get("ARENA_ONNX_DIR")

    @app.post("/predict/power", response_model=PowerPrediction)
    def predict_power(req: PowerRequest) -> PowerPrediction:
        """Probability from the exported LightGBM power model (ONNX Runtime). Research only."""
        if not onnx_dir:
            metrics.predictions.labels("no_model", "none").inc()
            raise HTTPException(status_code=503, detail="no ONNX model configured (ARENA_ONNX_DIR)")
        try:
            from arena.forecasters.onnx_power import OnnxPowerModel
        except ImportError as exc:  # pragma: no cover - runtime missing
            raise HTTPException(status_code=503, detail="onnxruntime is not installed") from exc
        nonlocal power_model
        if power_model is None:
            try:
                power_model = OnnxPowerModel(Path(onnx_dir))
            except (OSError, ValueError) as exc:
                raise HTTPException(
                    status_code=503, detail=f"model not loadable: {exc}"[:300]
                ) from exc
        try:
            out = power_model.probability(
                req.stat, req.daily, req.target_date, req.threshold, req.comparator
            )
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)[:300]) from exc
        metrics.predictions.labels("ok", power_model.version).inc()
        return PowerPrediction(**out)

    _mount_oracle(app, b)
    return app


def _mount_oracle(app: FastAPI, b: Benchmark) -> None:
    """Serve `arena-oracle` (A2A, read-only) at `/a2a` when the optional SDK is installed (T364).

    The card announces `ARENA_A2A_PUBLIC_URL` (default: this server on port 8000); the project's own
    client pins the interface to the URL it fetched the card from, so port mappings are harmless.
    """
    try:
        from arena.a2a.oracle import Oracle, build_oracle_app
    except ImportError:  # the A2A SDK is an optional requirement (requirements/a2a.txt)
        return
    docs = Path("docs")
    oracle = Oracle(b, _docs_index(docs) if (docs / "SPEC.md").is_file() else None)
    url = os.environ.get("ARENA_A2A_PUBLIC_URL", "http://127.0.0.1:8000/a2a/")
    app.mount("/a2a", build_oracle_app(oracle, url))


def _docs_index(root: Path) -> Any:
    from arena.lab.docs_assistant import DOC_PATHS, DocsIndex, load_chunks

    chunks = load_chunks(root.parent, [p for p in DOC_PATHS if (root.parent / p).is_file()])
    return DocsIndex(chunks) if chunks else None
