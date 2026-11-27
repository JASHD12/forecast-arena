"""`llm_context_cal` (T382): `llm_context`'s answers through a fixed logit map. Zero extra tokens.

Pre-registered in `lab/prereg/analyst-and-calibration.md` before the map was fitted: one logistic
(Platt) map `p' = sigmoid(a * logit(p) + b)`, fitted once by unpenalised logistic regression on
Claude Haiku's `llm_context` answers for 1,198 lab **training** questions
(`lab/data/distill-labels-v1.json`, outcomes from `lab/data/forecast-sft/train.jsonl.gz`), never on
live outcomes (I8). The fit is
`scripts/fit_llm_context_cal.py`; its result is the artefact `lab/artefacts/llm_context_cal.json`.

The map was fitted on power questions, so it is applied to power questions only; any other topic
passes the raw answer through unchanged (and the record says so). The forecaster reads the raw
answer from `ctx["peer_forecasts"]` like the ensemble, so it is listed after `llm_context` and costs
no tokens. A question `llm_context` did not answer (not in the daily sample, or a skip) is a
recorded skip, never a guess (I6). Experimental, flag `ARENA_LLM_CONTEXT_CAL` (off), outside the
headline board and the ensemble.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from arena.models import Forecast, Question, Skip

ARTEFACT = Path("lab/artefacts/llm_context_cal.json")
SOURCE_FORECASTER = "llm_context"
CALIBRATED_DOMAINS = frozenset({"power"})
CLIP = 0.01
VERSION_PREFIX = "cal-platt-r1"


def logit(p: float) -> float:
    """Log-odds of a probability clipped to [0.01, 0.99]."""
    q = min(1 - CLIP, max(CLIP, p))
    return math.log(q / (1 - q))


def sigmoid(z: float) -> float:
    """The logistic function."""
    return 1.0 / (1.0 + math.exp(-z))


@dataclass(frozen=True)
class CalMap:
    """The fitted map and where it came from."""

    a: float
    b: float
    n_train: int
    labels_sha256: str
    train_sha256: str

    @property
    def version(self) -> str:
        """Changes whenever the map changes."""
        h = hashlib.sha256(f"{self.a:.6f}|{self.b:.6f}|{self.labels_sha256}".encode()).hexdigest()
        return f"{VERSION_PREFIX}|{h[:8]}"

    def apply(self, p: float) -> float:
        """The calibrated probability, clipped to [0.01, 0.99]."""
        return min(1 - CLIP, max(CLIP, sigmoid(self.a * logit(p) + self.b)))


def fit_map(
    p: Sequence[float], y: Sequence[int], labels_sha256: str = "", train_sha256: str = ""
) -> CalMap:
    """Unpenalised logistic regression of the outcome on logit(p): the slope and the intercept."""
    from sklearn.linear_model import LogisticRegression

    if len(p) != len(y) or len(p) < 100 or len(set(y)) < 2:
        raise ValueError("need at least 100 answers with both outcomes to fit the map")
    x = np.array([[logit(v)] for v in p])
    clf = LogisticRegression(C=1e12, solver="lbfgs", max_iter=1000)  # effectively unpenalised
    clf.fit(x, np.asarray(y, dtype=int))
    return CalMap(
        float(clf.coef_[0, 0]), float(clf.intercept_[0]), len(p), labels_sha256, train_sha256
    )


def load_map(path: Path = ARTEFACT) -> CalMap | None:
    """The committed artefact, or None when absent (then the forecaster is not registered)."""
    if not path.is_file():
        return None
    d = json.loads(path.read_text("utf-8"))
    return CalMap(
        float(d["a"]),
        float(d["b"]),
        int(d["n_train"]),
        str(d["labels_sha256"]),
        str(d["train_sha256"]),
    )


class LLMContextCal:
    """`llm_context_cal`: the calibrated copy of the raw `llm_context` answer."""

    forecaster_id = "llm_context_cal"
    needs_peers = True  # reads `llm_context` from `ctx["peer_forecasts"]` (listed after it)

    def __init__(self, cal: CalMap) -> None:
        self.cal = cal

    def version(self) -> str:
        """The map version."""
        return self.cal.version

    def _skip(self, q: Question, asof: datetime, reason: str, detail: str) -> Skip:
        return Skip(
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=self.version(),
            reason_code=reason,  # type: ignore[arg-type]
            detail=detail[:300],
            created_at=asof,
        )

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        raw = ctx.get("peer_forecasts", {}).get(SOURCE_FORECASTER)
        if raw is None:
            return self._skip(
                q, asof, "not_sampled", f"no {SOURCE_FORECASTER} answer for this question"
            )
        applied = q.domain in CALIBRATED_DOMAINS
        p = self.cal.apply(float(raw)) if applied else float(raw)
        return Forecast(
            forecast_id=f"{q.question_id}::{self.forecaster_id}",
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=self.version(),
            probability=p,
            created_at=asof,
            meta={
                "raw": round(float(raw), 6),
                "calibrated": applied,
                "a": round(self.cal.a, 6),
                "b": round(self.cal.b, 6),
            },
        )
