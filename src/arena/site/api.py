"""Static JSON API (T139): `api/v1/{questions,latest,leaderboard}.json` plus a JSON Schema
for each, generated from the same pydantic models that build the files.

Static files on GitHub Pages: no server, no keys, cacheable. Every value is derived from
the ledger at build time (I5). The leaderboard file says which scope it covers (official
record or rehearsal) and carries the same "too early to tell" label as the site.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from arena.scoring.boards import Board
from arena.scoring.core import Record
from arena.site.titles import plain_title

API_VERSION = "v1"


class ForecastOut(BaseModel):
    """One published forecast."""

    forecaster_id: str
    forecaster_version: str
    probability: float = Field(ge=0, le=1, description="Published P(YES), not clipped")
    created_at: datetime = Field(description="Always before the question's lock_time")


class QuestionOut(BaseModel):
    """One question with its forecasts and, once known, its outcome."""

    question_id: str
    domain: str
    title: str
    text: str
    batch_date: date
    target_date: date
    lock_time: datetime
    status: Literal["open", "resolved", "void"]
    outcome: Literal[0, 1] | None = Field(None, description="1 = YES, 0 = NO; null if open")
    forecasts: list[ForecastOut]
    url: str = Field(description="The question page, relative to the site root")


class QuestionsFile(BaseModel):
    """Every question, newest first."""

    api_version: str = API_VERSION
    generated_at: datetime
    questions: list[QuestionOut]


class LeaderboardRow(BaseModel):
    """One forecaster on the headline board."""

    forecaster_id: str
    n: int
    brier: float
    brier_low: float = Field(description="95% day-block bootstrap interval, lower end")
    brier_high: float
    log_score: float
    brier_minus_base_rate: float | None = Field(
        None, description="Paired difference to base_rate on the same questions (negative = better)"
    )


class LeaderboardFile(BaseModel):
    """The headline all-questions board (official record, or rehearsal before it starts)."""

    api_version: str = API_VERSION
    generated_at: datetime
    scope: Literal["official", "rehearsal"]
    label: str | None = Field(description='e.g. "too early to tell"')
    questions: int
    days: int
    rows: list[LeaderboardRow]


def _question(rec: Record, qid: str, url: str) -> QuestionOut:
    q = rec.questions[qid]
    res, void = rec.resolutions.get(qid), rec.voids.get(qid)
    fs = sorted((f for f in rec.forecasts if f.question_id == qid), key=lambda f: f.forecaster_id)
    return QuestionOut(
        question_id=qid, domain=q.domain, title=plain_title(q), text=q.text,
        batch_date=q.batch_date, target_date=q.target_date, lock_time=q.lock_time,
        status="void" if void else "resolved" if res else "open",
        outcome=None if res is None or void else res.outcome,
        forecasts=[ForecastOut(forecaster_id=f.forecaster_id,
                               forecaster_version=f.forecaster_version,
                               probability=f.probability, created_at=f.created_at) for f in fs],
        url=url,
    )  # fmt: skip


def build_api(
    out_dir: Path, rec: Record, board: Board | None, scope: Literal["official", "rehearsal"],
    now: datetime, href: Any,
) -> list[str]:  # fmt: skip
    """Write the three files and their schemas under `out_dir/api/v1`; returns their paths."""
    base = out_dir / "api" / API_VERSION
    (base / "schema").mkdir(parents=True, exist_ok=True)
    qs = sorted(rec.questions.values(), key=lambda q: (q.batch_date, q.question_id), reverse=True)
    items = [_question(rec, q.question_id, href(q.question_id)) for q in qs]
    allq = QuestionsFile(generated_at=now, questions=items)
    latest_day = qs[0].batch_date if qs else None
    newest = [x for x in items if x.batch_date == latest_day]
    latest = QuestionsFile(generated_at=now, questions=newest)
    rows = []
    if board is not None:
        for r in board.rows:
            rows.append(LeaderboardRow(
                forecaster_id=r.forecaster_id, n=r.n, brier=r.brier.estimate,
                brier_low=r.brier.low, brier_high=r.brier.high, log_score=r.log,
                brier_minus_base_rate=None if r.vs_reference is None else r.vs_reference.estimate,
            ))  # fmt: skip
    lb = LeaderboardFile(generated_at=now, scope=scope, label=board.label if board else None,
                         questions=board.questions if board else 0,
                         days=board.days if board else 0, rows=rows)  # fmt: skip
    files = {"questions": allq, "latest": latest, "leaderboard": lb}
    out = []
    for name, model in files.items():
        (base / f"{name}.json").write_text(model.model_dump_json(indent=1) + "\n", encoding="utf-8")
        schema = type(model).model_json_schema()
        schema["$id"] = f"api/{API_VERSION}/schema/{name}.schema.json"
        (base / "schema" / f"{name}.schema.json").write_text(
            json.dumps(schema, indent=1, sort_keys=True) + "\n", encoding="utf-8")  # fmt: skip
        out += [f"api/{API_VERSION}/{name}.json", f"api/{API_VERSION}/schema/{name}.schema.json"]
    return out


ENDPOINTS = (
    ("questions", "Every question, newest first, with every forecast and the outcome."),
    ("latest", "Only the most recent batch day (small; good for polling once a day)."),
    ("leaderboard", "The headline all-questions board with 95% intervals and its scope."),
)
