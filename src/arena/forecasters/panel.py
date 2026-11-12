"""`human_panel` (SPEC 8.7): intake from a published CSV, validation, pseudonyms, median.

CSV columns (header required): `token,question_id,probability,submitted_at`
(`submitted_at` in ISO 8601 with a UTC offset). Rules:
- a token maps to the pseudonym `panel-` + the first 8 hex characters of its SHA-256;
  tokens never leave this module and no names or emails are stored;
- if an allowlist of token SHA-256 hashes is configured, other tokens are rejected;
- rows submitted at or after the question's lock time are ignored;
- the latest valid row per person per question wins;
- the panel forecast is the median of the members' probabilities when at least 3 people
  answered; otherwise no forecast (a `not_sampled` skip with the count).
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from arena.clock import ensure_utc
from arena.models import Forecast, Question, Skip

COLUMNS = ("token", "question_id", "probability", "submitted_at")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{12,64}$")
MIN_MEMBERS = 3
VERSION = "panel-median-r1"


def pseudonym(token: str) -> str:
    """`panel-` + first 8 hex of SHA-256(token)."""
    return "panel-" + hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


def token_hash(token: str) -> str:
    """Full SHA-256 of a token (what an allowlist stores)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Row:
    """One valid submission (token already replaced by its pseudonym)."""

    member: str
    question_id: str
    probability: float
    submitted_at: datetime


@dataclass
class Intake:
    """Parsed submissions and the reasons rows were rejected (no token values kept)."""

    rows: list[Row] = field(default_factory=list)
    rejected: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str) -> None:
        """Count a rejected row."""
        self.rejected[reason] = self.rejected.get(reason, 0) + 1


def parse_panel_csv(text: str, allowlist: set[str] | None = None) -> Intake:
    """Validate the CSV. Bad rows are counted by reason, never guessed."""
    out = Intake()
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or tuple(f.strip() for f in reader.fieldnames) != COLUMNS:
        raise ValueError(f"panel CSV must have the header {','.join(COLUMNS)}")
    for raw in reader:
        tok = (raw.get("token") or "").strip()
        if not TOKEN_RE.match(tok):
            out.reject("bad_token")
            continue
        if allowlist is not None and token_hash(tok) not in allowlist:
            out.reject("unknown_token")
            continue
        try:
            p = float((raw.get("probability") or "").strip())
            when = ensure_utc(datetime.fromisoformat((raw.get("submitted_at") or "").strip()))
        except ValueError:
            out.reject("bad_value")
            continue
        if not 0.0 <= p <= 1.0 or p != p:
            out.reject("bad_probability")
            continue
        qid = (raw.get("question_id") or "").strip()
        if not qid:
            out.reject("bad_value")
            continue
        out.rows.append(Row(pseudonym(tok), qid, p, when))
    return out


def latest_by_member(rows: Iterable[Row], q: Question) -> dict[str, Row]:
    """Latest valid row per member for one question, ignoring rows at or after lock."""
    best: dict[str, Row] = {}
    for r in rows:
        if r.question_id != q.question_id or r.submitted_at >= q.lock_time:
            continue
        cur = best.get(r.member)
        if cur is None or r.submitted_at > cur.submitted_at:
            best[r.member] = r
    return best


class HumanPanel:
    """Median of panel members' probabilities (at least 3 answers)."""

    forecaster_id = "human_panel"

    def __init__(self, intake: Intake | None) -> None:
        self.intake = intake

    def version(self) -> str:
        """Aggregation rule version."""
        return VERSION

    def forecast(self, q: Question, ctx: Mapping[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        if self.intake is None:
            return Skip(
                question_id=q.question_id,
                forecaster_id=self.forecaster_id,
                forecaster_version=VERSION,
                reason_code="model_missing",
                detail="no panel CSV configured",
                created_at=asof,
            )
        rows = latest_by_member((r for r in self.intake.rows if r.submitted_at <= asof), q)
        if len(rows) < MIN_MEMBERS:
            return Skip(
                question_id=q.question_id,
                forecaster_id=self.forecaster_id,
                forecaster_version=VERSION,
                reason_code="not_sampled",
                detail=f"{len(rows)} panel answers (needs {MIN_MEMBERS})",
                created_at=asof,
            )
        p = statistics.median(r.probability for r in rows.values())
        return Forecast(
            forecast_id=f"{q.question_id}::{self.forecaster_id}",
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=VERSION,
            probability=p,
            created_at=asof,
            meta={"members": sorted(rows), "n": len(rows)},
        )
