"""`ensemble` (SPEC 8.6): a logistic regression on the other forecasters' logits.

Inputs are the probabilities of the common-set members (`base_rate`, `ml`,
`llm_context`, `agent`; `llm_plain` was retired on 2026-11-27) for the same question, as logits,
plus one indicator per domain.
It is retrained weekly on resolved **official-record** forecasts only (an expanding window;
rehearsal days never train it) and stays inactive until at least 300 resolved common-set
forecasts exist (the same threshold the common-set board uses to drop its "too early" label).

Everything that could leak is excluded by construction:
- training rows come from questions of batch days up to `TRAIN_LAG_DAYS` before the start of
  the current ISO week, so their outcomes were known when the weekly model was fitted;
- a question needs every member's forecast to become a row (the common set);
- at forecast time the member probabilities come from forecasts already written for the same
  question, never from later ones.

Below the threshold the forecaster is simply not registered (it is not a failure); when it
is registered but a question lacks a member's forecast it records a `model_missing` skip.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

from arena.models import Forecast, Question, Skip
from arena.scoring.boards import COMMON_GROUP, MIN_COMMON
from arena.scoring.core import Scored

MEMBERS: tuple[str, ...] = COMMON_GROUP
TRAIN_LAG_DAYS = 2
CLIP = 0.01
REVISION = 1


def logit(p: float) -> float:
    """Log-odds of a probability clipped to [0.01, 0.99]."""
    q = min(1 - CLIP, max(CLIP, p))
    return math.log(q / (1 - q))


def week_start(day: date) -> date:
    """Monday of the ISO week containing `day`."""
    return day - timedelta(days=day.weekday())


@dataclass(frozen=True)
class Row:
    """One training row: a question every member answered, and its outcome."""

    question_id: str
    domain: str
    batch_date: date
    probs: Mapping[str, float]
    outcome: int


def common_rows(scored: Sequence[Scored], members: Sequence[str] = MEMBERS) -> list[Row]:
    """Questions answered by every member, as rows (one row per question)."""
    by_q: dict[str, dict[str, Scored]] = defaultdict(dict)
    for s in scored:
        if s.forecaster_id in members:
            by_q[s.question_id][s.forecaster_id] = s
    rows = []
    for qid, m in sorted(by_q.items()):
        if all(f in m for f in members):
            first = m[members[0]]
            rows.append(
                Row(qid, first.domain, first.batch_date, {f: m[f].probability for f in members},
                    first.outcome)
            )  # fmt: skip
    return rows


def training_cutoff(asof: datetime) -> date:
    """Last batch day that may train the model fitted for the week containing `asof`."""
    return week_start(asof.date()) - timedelta(days=TRAIN_LAG_DAYS)


def eligible_rows(
    scored: Sequence[Scored], official_start: date | None, asof: datetime
) -> list[Row]:
    """Official-record rows that were resolved before this week's fit (none before the start)."""
    if official_start is None:
        return []
    cutoff = training_cutoff(asof)
    official = [s for s in scored if s.batch_date >= official_start and s.batch_date <= cutoff]
    return common_rows(official)


def is_active(rows: Sequence[Row], members: Sequence[str] = MEMBERS) -> bool:
    """The activation threshold: at least `MIN_COMMON` resolved common-set forecasts."""
    return len(rows) * len(members) >= MIN_COMMON


class EnsembleModel:
    """The fitted logistic regression and its feature layout."""

    def __init__(self, domains: Sequence[str], members: Sequence[str], train_end: date, n: int):
        self.domains = tuple(sorted(domains))
        self.members = tuple(members)
        self.train_end = train_end
        self.n = n
        self.clf = LogisticRegression(C=1.0, max_iter=1000)

    def features(self, probs: Mapping[str, float], domain: str) -> list[float]:
        """Logits of the members, then domain indicators."""
        return [logit(probs[f]) for f in self.members] + [
            1.0 if domain == d else 0.0 for d in self.domains
        ]

    def fit(self, rows: Sequence[Row]) -> EnsembleModel:
        """Fit on `rows`; needs both outcomes present."""
        y = np.array([r.outcome for r in rows])
        if len(set(y.tolist())) < 2:
            raise ValueError("training rows contain a single outcome")
        x = np.array([self.features(r.probs, r.domain) for r in rows])
        self.clf.fit(x, y)
        return self

    def probability(self, probs: Mapping[str, float], domain: str) -> float:
        """P(YES) for one question."""
        x = np.array([self.features(probs, domain)])
        return float(self.clf.predict_proba(x)[0, 1])

    @property
    def version(self) -> str:
        """Changes whenever the training set changes."""
        return f"ensemble-lr-r{REVISION}-{self.train_end.isoformat()}-n{self.n}"


def train(
    scored: Sequence[Scored], official_start: date | None, asof: datetime
) -> EnsembleModel | None:
    """The ensemble for the week containing `asof`, or None while it is inactive."""
    rows = eligible_rows(scored, official_start, asof)
    if not is_active(rows):
        return None
    domains = sorted({r.domain for r in rows})
    try:
        return EnsembleModel(domains, MEMBERS, training_cutoff(asof), len(rows)).fit(rows)
    except ValueError:
        return None


class EnsembleForecaster:
    """`ensemble`: combines the other forecasters' forecasts of the same question."""

    forecaster_id = "ensemble"
    needs_peers = True  # the morning job passes `ctx["peer_forecasts"]`

    def __init__(self, model: EnsembleModel) -> None:
        self.model = model

    def version(self) -> str:
        """The model version."""
        return self.model.version

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        peers: Mapping[str, float] = ctx.get("peer_forecasts", {})
        missing = [f for f in self.model.members if f not in peers]
        if missing:
            return Skip(
                question_id=q.question_id,
                forecaster_id=self.forecaster_id,
                forecaster_version=self.version(),
                reason_code="model_missing",
                detail=f"no forecast from {', '.join(missing)} for this question"[:300],
                created_at=asof,
            )
        if q.domain not in self.model.domains:
            return Skip(
                question_id=q.question_id,
                forecaster_id=self.forecaster_id,
                forecaster_version=self.version(),
                reason_code="model_missing",
                detail=f"domain {q.domain} was not in the training rows",
                created_at=asof,
            )
        p = self.model.probability(peers, q.domain)
        return Forecast(
            forecast_id=f"{q.question_id}::{self.forecaster_id}",
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=self.version(),
            probability=p,
            created_at=asof,
            meta={"inputs": {f: round(peers[f], 6) for f in self.model.members}},
        )
