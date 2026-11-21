"""`llm_router`: a cascade over the other forecasters (T273, experimental).

A production pattern for cutting cost: answer with a cheap model when it is sure, and pay for
a stronger one only when it is not. Here the cheap tier is the gradient-boosted `ml` model and
the fine-tuned local model (both free); the strong tier is `llm_context` (paid). For each
question the router looks at the forecasts the others already wrote:

- if every available cheap forecast is decisive (`|p - 0.5| >= delta`) and, with two of them,
  they agree (`|ml - ft| <= gamma`): the answer is the mean of the cheap forecasts and the paid
  call is *avoided*;
- otherwise it takes `llm_context`'s answer ("escalated").

It adds no model calls: the paid forecast exists anyway for the shared daily sample, so the
router measures live, on the same questions, what a cascade would have saved
(`paid_calls_avoided`) and what that costs in Brier score. `delta` and `gamma` were chosen on
validation days only and are frozen in the version string (`lab/artefacts/llm_router.json`);
until that file exists the router is not registered.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from arena.models import Forecast, Question, Skip

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "lab" / "artefacts" / "llm_router.json"
CHEAP = ("ml", "llm_local_ft")
STRONG = "llm_context"


@dataclass(frozen=True)
class RouterParams:
    """The frozen thresholds and where they came from."""

    delta: float
    gamma: float
    chosen_on: str  # "validation days 2026-07-01 to 2026-09-30"
    prereg_sha256: str


def load_params(path: Path = DEFAULT_PATH) -> RouterParams | None:
    """The committed thresholds, or None (the router is then not registered)."""
    if not path.is_file():
        return None
    return RouterParams(**json.loads(path.read_text(encoding="utf-8")))


class RouterForecaster:
    """`llm_router`; reads `ctx["peer_forecasts"]` like the ensemble."""

    forecaster_id = "llm_router"
    needs_peers = True  # the morning job passes `ctx["peer_forecasts"]`

    def __init__(self, params: RouterParams) -> None:
        self.params = params

    def version(self) -> str:
        """Thresholds and tiers (SPEC 8.5): any change is a new version."""
        p = self.params
        return f"router-r1|delta-{p.delta:.3f}|gamma-{p.gamma:.3f}|{'+'.join(CHEAP)}>{STRONG}"

    def _skip(self, q: Question, detail: str, asof: datetime) -> Skip:
        return Skip(
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=self.version(),
            reason_code="model_missing",
            detail=detail[:300],
            created_at=asof,
        )

    def decide(self, peers: Mapping[str, float]) -> tuple[float, dict[str, Any]] | None:
        """(probability, meta) from the peers' forecasts, or None if nothing to answer with."""
        p = self.params
        cheap = {f: peers[f] for f in CHEAP if f in peers}
        strong = peers.get(STRONG)
        sure = bool(cheap) and all(abs(v - 0.5) >= p.delta for v in cheap.values())
        agree = len(cheap) < 2 or max(cheap.values()) - min(cheap.values()) <= p.gamma
        meta: dict[str, Any] = {"cheap": {f: round(v, 6) for f, v in cheap.items()}}
        if sure and agree:
            meta.update(escalated=False, paid_calls_avoided=1 if strong is not None else 0)
            return sum(cheap.values()) / len(cheap), meta
        if strong is not None:
            meta.update(escalated=True, paid_calls_avoided=0)
            return strong, meta
        return None

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        peers: Mapping[str, float] = ctx.get("peer_forecasts", {})
        out = self.decide(peers)
        if out is None:
            return self._skip(
                q, "no cheap forecast was decisive and no llm_context forecast exists", asof
            )
        prob, meta = out
        return Forecast(
            forecast_id=f"{q.question_id}::{self.forecaster_id}",
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=self.version(),
            probability=min(0.99, max(0.01, prob)),
            created_at=asof,
            meta={**meta, "experimental": True},
        )
