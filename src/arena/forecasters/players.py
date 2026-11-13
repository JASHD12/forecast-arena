"""Public players (T161, SPEC 8.8): intake from the published form CSV.

CSV columns (header required): `code,question_id,probability,submitted_at,consent`.

- `code` is a random player code the player chooses or is given by the form (12-64 of
  A-Z, a-z, 0-9, `_`, `-`). It never leaves this module: a player appears only as
  `player_` + the first 8 hex characters of SHA-256(code). No nicknames, names or emails
  are read or stored. A player can find their own id from their code (the Play page says
  how), nobody else can reverse it.
- `consent` must be `yes` (the form's consent tick-box, H15); other rows are rejected.
- `probability` in [0, 1]; `submitted_at` ISO 8601 with a UTC offset.
- Rows submitted at or after the question's lock, or after the intake run itself, do not
  count. For each player and question the latest valid row before the intake wins.
- The intake writes one forecast per player and question into `players/B.jsonl` before
  the lock. A forecast once written is never replaced (append-only): a second intake run
  only adds players and questions that are not in the file yet.
- Rejected rows are counted by reason only; no row content is kept.
- A player is ranked only after `MIN_RANKED_ANSWERS` resolved answers (T162).
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from arena.clock import ensure_utc
from arena.forecasters.panel import TOKEN_RE
from arena.models import Forecast, Question

COLUMNS = ("code", "question_id", "probability", "submitted_at", "consent")
PREFIX = "player_"
VERSION = "player-r1"
#: Resolved answers a player needs before appearing on the players' leaderboard.
MIN_RANKED_ANSWERS = 10


def player_id(code: str) -> str:
    """`player_` + the first 8 hex characters of SHA-256(code)."""
    return PREFIX + hashlib.sha256(code.encode("utf-8")).hexdigest()[:8]


def is_player(forecaster_id: str) -> bool:
    """True for a public player's id (never one of the machine forecasters)."""
    return forecaster_id.startswith(PREFIX)


@dataclass(frozen=True)
class Submission:
    """One valid row; the code is already replaced by the player id."""

    player: str
    question_id: str
    probability: float
    submitted_at: datetime


@dataclass
class PlayerIntake:
    """Valid submissions and rejection counts by reason."""

    rows: list[Submission] = field(default_factory=list)
    rejected: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str, n: int = 1) -> None:
        """Count rejected rows."""
        self.rejected[reason] = self.rejected.get(reason, 0) + n


def parse_players_csv(text: str) -> PlayerIntake:
    """Validate the form CSV. Bad rows are counted, never repaired or guessed."""
    out = PlayerIntake()
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or tuple(f.strip() for f in reader.fieldnames) != COLUMNS:
        raise ValueError(f"players CSV must have the header {','.join(COLUMNS)}")
    for raw in reader:
        code = (raw.get("code") or "").strip()
        if not TOKEN_RE.match(code):
            out.reject("bad_code")
            continue
        if (raw.get("consent") or "").strip().lower() != "yes":
            out.reject("no_consent")
            continue
        qid = (raw.get("question_id") or "").strip()
        try:
            p = float((raw.get("probability") or "").strip())
            when = ensure_utc(datetime.fromisoformat((raw.get("submitted_at") or "").strip()))
        except ValueError:
            out.reject("bad_value")
            continue
        if not qid:
            out.reject("bad_value")
            continue
        if p != p or not 0.0 <= p <= 1.0:
            out.reject("bad_probability")
            continue
        out.rows.append(Submission(player_id(code), qid, p, when))
    return out


def select(
    intake: PlayerIntake, questions: Sequence[Question], asof: datetime
) -> tuple[dict[tuple[str, str], Submission], dict[str, int]]:
    """The latest valid row per (question, player) before both the lock and `asof`.

    Returns the winners and counts of rows that did not count: `late` (at or after the
    lock), `after_intake` (after `asof`, e.g. a clock skew), `other_question` (not a
    question of this batch) and `superseded` (an older row of the same player).
    """
    by_id = {q.question_id: q for q in questions}
    best: dict[tuple[str, str], Submission] = {}
    dropped: dict[str, int] = {}

    def drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    for r in intake.rows:
        q = by_id.get(r.question_id)
        if q is None:
            drop("other_question")
        elif r.submitted_at >= q.lock_time:
            drop("late")
        elif r.submitted_at > asof:
            drop("after_intake")
        else:
            k = (r.question_id, r.player)
            cur = best.get(k)
            if cur is None or r.submitted_at > cur.submitted_at:
                if cur is not None:
                    drop("superseded")
                best[k] = r
            else:
                drop("superseded")
    return best, dropped


def to_forecasts(
    winners: Mapping[tuple[str, str], Submission], created_at: datetime, skip_ids: Iterable[str]
) -> list[Forecast]:
    """Forecast records for winners whose id is not already in the ledger."""
    have = set(skip_ids)
    out = []
    for (qid, player), s in sorted(winners.items()):
        fid = f"{qid}::{player}"
        if fid in have:
            continue
        out.append(
            Forecast(
                forecast_id=fid,
                question_id=qid,
                forecaster_id=player,
                forecaster_version=VERSION,
                probability=s.probability,
                created_at=created_at,
                meta={"submitted_at": s.submitted_at.isoformat()},
            )
        )
    return out
