"""`sentiment` (T373, SPEC 8): crypto questions from GDELT news tone and article volume.

Experimental, flag ``ARENA_SENTIMENT`` (off), outside the headline board and the ensemble.
Version ``sentiment-gdelt-r1``, pre-registered in ``lab/prereg/sentiment.md`` before any
backtest. GDELT only (no Reddit, no X; DECISIONS 2026-11-27).

Per template (``bigmove``, ``up``) one L2 logistic regression (C = 1, standardised inputs) on

- ``tone``: the average tone of the latest known day (day B-2 at the morning run, see
  ``arena.sources.gdelt_tone``),
- ``tone_chg``: that tone minus the mean tone of the 7 days before it,
- ``vol_chg``: ln((articles + 1) / (mean articles of the 7 days before + 1)),
- for ``bigmove`` also ``logit(p_ml)``: the probability of `ml` (``crypto-ewma-t5-r1``) for the
  same question, read from ``ctx["peer_forecasts"]`` like the ensemble does.

The GDELT numbers come from ``ctx["gdelt"]`` (aggregates only, no article text), which the
morning job snapshots, so the record is auditable (I3). A question without usable GDELT
numbers, a missing `ml` probability or a missing model is a recorded skip, never a guess (I6).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from arena.models import Forecast, Question, Skip
from arena.sources import gdelt_tone as G

VERSION = "sentiment-gdelt-r1"
TEMPLATES = ("bigmove", "up")
FEATURES: dict[str, tuple[str, ...]] = {
    "bigmove": ("tone", "tone_chg", "vol_chg", "logit_ml"),
    "up": ("tone", "tone_chg", "vol_chg"),
}
PRIOR_DAYS = 7
MIN_PRIOR = 4
C = 1.0
MIN_TRAIN = 60
CLIP = 0.02
CONTEXT_DAYS = 15


def logit(p: float) -> float:
    """Log-odds of a probability clipped to [0.01, 0.99]."""
    q = min(0.99, max(0.01, p))
    return math.log(q / (1 - q))


def gdelt_context(
    tone: Mapping[date, float],
    count: Mapping[date, int],
    covered_count: set[date],
    asof: datetime,
) -> dict[str, Any] | None:
    """The aggregates known at `asof` for the morning context (no texts), or None.

    `covered_count` are the days whose article counts were recorded; a covered day without an
    entry in `count` had no matching articles (count 0), an uncovered day is unknown.
    """
    last = G.known_days(asof)
    first = last - timedelta(days=CONTEXT_DAYS - 1)
    days = [first + timedelta(days=i) for i in range(CONTEXT_DAYS)]
    tone_rows = [[d.isoformat(), tone[d]] for d in days if d in tone]
    count_rows = [
        [d.isoformat(), count.get(d, 0)] for d in days if d in covered_count or d in count
    ]
    if not tone_rows and not count_rows:
        return None
    return {
        "source": G.ATTRIBUTION,
        "last_known_day": last.isoformat(),
        "tone": tone_rows,
        "count": count_rows,
    }


def features(
    template: str, gdelt: Mapping[str, Any] | None, p_ml: float | None
) -> tuple[list[float] | None, str]:
    """Feature vector of one question, or (None, why not)."""
    if not gdelt:
        return None, "no GDELT numbers in the context"
    last = date.fromisoformat(str(gdelt["last_known_day"]))
    tone = {date.fromisoformat(d): float(v) for d, v in gdelt.get("tone", [])}
    count = {date.fromisoformat(d): float(v) for d, v in gdelt.get("count", [])}
    if last not in tone:
        return None, f"no news tone for {last} (no articles or not recorded)"
    if last not in count:
        return None, f"no article count for {last}"
    prior = [last - timedelta(days=i) for i in range(1, PRIOR_DAYS + 1)]
    t_prior = [tone[d] for d in prior if d in tone]
    c_prior = [count[d] for d in prior if d in count]
    if len(t_prior) < MIN_PRIOR or len(c_prior) < MIN_PRIOR:
        return None, "fewer than 4 of the 7 earlier days have GDELT numbers"
    tone_chg = tone[last] - sum(t_prior) / len(t_prior)
    vol_chg = math.log((count[last] + 1.0) / (sum(c_prior) / len(c_prior) + 1.0))
    vec = [tone[last], tone_chg, vol_chg]
    if template == "bigmove":
        if p_ml is None:
            return None, "no ml probability for this question"
        vec.append(logit(p_ml))
    return vec, ""


@dataclass
class SentimentModel:
    """A fitted logistic model of one template."""

    template: str
    scaler: StandardScaler
    clf: LogisticRegression
    n_train: int
    version: str = VERSION

    def probability(self, x: Sequence[float]) -> float:
        """P(YES), clipped to [0.02, 0.98]."""
        z = self.scaler.transform(np.asarray([x], dtype=float))
        p = float(self.clf.predict_proba(z)[0, 1])
        return min(1 - CLIP, max(CLIP, p))


def fit(template: str, x: Sequence[Sequence[float]], y: Sequence[int]) -> SentimentModel | None:
    """Fit the model, or None when there are too few rows or only one outcome class."""
    if template not in FEATURES:
        raise ValueError(f"unknown template {template!r}")
    if len(y) < MIN_TRAIN or len(set(y)) < 2:
        return None
    arr = np.asarray(x, dtype=float)
    if arr.shape[1] != len(FEATURES[template]):
        raise ValueError(f"expected {len(FEATURES[template])} features, got {arr.shape[1]}")
    scaler = StandardScaler().fit(arr)
    clf = LogisticRegression(C=C, solver="lbfgs", max_iter=1000)
    clf.fit(scaler.transform(arr), np.asarray(y, dtype=int))
    return SentimentModel(template, scaler, clf, len(y))


class SentimentForecaster:
    """`sentiment`: the fitted models applied to the GDELT numbers of the morning context."""

    forecaster_id = "sentiment"
    needs_peers = True  # reads `ml` from `ctx["peer_forecasts"]` (listed after `ml`)

    def __init__(self, models: Mapping[str, SentimentModel]) -> None:
        self.models = dict(models)

    def version(self) -> str:
        """The pre-registered model version."""
        return VERSION

    def _skip(self, q: Question, asof: datetime, detail: str) -> Skip:
        return Skip(
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=VERSION,
            reason_code="model_missing",
            detail=detail[:300],
            created_at=asof,
        )

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        if q.domain != "crypto" or q.template not in self.models:
            return self._skip(q, asof, f"no model for {q.domain}/{q.template}")
        peers: Mapping[str, float] = ctx.get("peer_forecasts", {})
        vec, why = features(q.template, ctx.get("gdelt"), peers.get("ml"))
        if vec is None:
            return self._skip(q, asof, why)
        p = self.models[q.template].probability(vec)
        return Forecast(
            forecast_id=f"{q.question_id}::{self.forecaster_id}",
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=VERSION,
            probability=p,
            created_at=asof,
            meta={
                "features": dict(
                    zip(FEATURES[q.template], (round(v, 6) for v in vec), strict=True)
                ),
                "n_train": self.models[q.template].n_train,
            },
        )
