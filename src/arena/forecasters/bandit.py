"""`bandit_hedge`: online learning of which forecaster to trust, per topic (T293, experimental).

An *expert-advice* forecaster, the production-style form of reinforcement learning for this
project: there is no environment to explore, only a stream of resolved questions that reveal how
well each peer forecaster did. The Hedge algorithm (Freund and Schapire, 1997) keeps one weight per
expert and topic, proportional to `exp(-eta * cumulative loss)`, and answers with the weighted mean
of the peers' probabilities for the question. A Thompson-sampling variant (`thompson_pick`) is used
in the replay study to compare "blend" with "pick one".

Leakage and restartability: the weights are a pure function of resolved forecasts of questions
whose batch day is at least `LAG_DAYS` before the forecast day (their outcomes were known), so the
job is idempotent and nothing is stored between days. Nothing is tuned on a specific live question
(I8): `eta` follows the textbook rule from the number of rounds, and the loss is the Brier score.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from arena.models import Forecast, Question, Skip
from arena.scoring.core import Scored

#: The experts: forecasters that answer (almost) every question or a seeded daily sample.
EXPERTS: tuple[str, ...] = ("base_rate", "ml", "llm_plain", "llm_context", "agent")
LAG_DAYS = 2
SHRINK = 5  # pseudo-rounds at the coin-flip loss 0.25 so a rarely-seen expert is not over-trusted
PRIOR_LOSS = 0.25
CLIP = 0.01
REVISION = 1


def brier_loss(p: float, y: int) -> float:
    """Squared error of a probability."""
    return (p - y) ** 2


def hedge_eta(rounds: int, k: int) -> float:
    """Hedge's learning rate for losses in [0, 1]: sqrt(8 ln K / T), capped for tiny T."""
    return min(2.0, math.sqrt(8 * math.log(max(k, 2)) / max(rounds, 1)))


@dataclass
class HedgeModel:
    """Per-topic cumulative (shrunk) losses and the weights they imply."""

    experts: tuple[str, ...] = EXPERTS
    #: domain -> expert -> (sum of Brier losses, number of answered questions)
    stats: dict[str, dict[str, tuple[float, int]]] = field(default_factory=dict)
    #: domain -> number of resolved questions that any expert answered
    rounds: dict[str, int] = field(default_factory=dict)

    def weights(self, domain: str, available: Sequence[str] | None = None) -> dict[str, float]:
        """Normalised Hedge weights of the available experts in a topic."""
        names = [e for e in (available or self.experts) if e in self.experts]
        if not names:
            return {}
        t = self.rounds.get(domain, 0)
        if t == 0:
            return {e: 1 / len(names) for e in names}  # the uniform prior, recorded as rounds=0
        eta = hedge_eta(t, len(self.experts))
        loss = {}
        for e in names:
            s, n = self.stats.get(domain, {}).get(e, (0.0, 0))
            mean = (s + SHRINK * PRIOR_LOSS) / (n + SHRINK)
            loss[e] = mean * t  # cumulative loss if the expert had answered every round
        low = min(loss.values())
        raw = {e: math.exp(-eta * (v - low)) for e, v in loss.items()}
        z = sum(raw.values())
        return {e: v / z for e, v in raw.items()}

    def predict(self, domain: str, peers: Mapping[str, float]) -> tuple[float, dict[str, float]]:
        """(blended probability, weights used) from the peers' forecasts of one question."""
        w = self.weights(domain, [e for e in peers if e in self.experts])
        p = sum(w[e] * peers[e] for e in w)
        return min(1 - CLIP, max(CLIP, p)), w


def train(
    scored: Sequence[Scored], asof: datetime, experts: tuple[str, ...] = EXPERTS
) -> HedgeModel:
    """The model at `asof`: only questions whose batch day is at least LAG_DAYS earlier count."""
    cutoff: date = asof.date() - timedelta(days=LAG_DAYS)
    stats: dict[str, dict[str, list[float]]] = defaultdict(dict)
    seen: dict[str, set[str]] = defaultdict(set)
    for s in scored:
        if s.batch_date > cutoff or s.forecaster_id not in experts:
            continue
        cell = stats[s.domain].setdefault(s.forecaster_id, [0.0, 0])
        cell[0] += brier_loss(s.probability, s.outcome)
        cell[1] += 1
        seen[s.domain].add(s.question_id)
    return HedgeModel(
        experts,
        {d: {e: (c[0], int(c[1])) for e, c in cells.items()} for d, cells in stats.items()},
        {d: len(q) for d, q in seen.items()},
    )


def thompson_pick(
    domain: str,
    scored: Sequence[Scored],
    asof: datetime,
    seed: str,
    experts: Sequence[str] = EXPERTS,
) -> str:
    """Thompson sampling over experts: sample each expert's chance of beating 0.25 on a question
    from a Beta posterior of its wins and losses, and return the best draw (seeded, so a replay
    gives the same pick)."""
    cutoff = asof.date() - timedelta(days=LAG_DAYS)
    wins = {e: 1.0 for e in experts}
    losses = {e: 1.0 for e in experts}
    for s in scored:
        if s.domain != domain or s.batch_date > cutoff or s.forecaster_id not in wins:
            continue
        if brier_loss(s.probability, s.outcome) < PRIOR_LOSS:
            wins[s.forecaster_id] += 1
        else:
            losses[s.forecaster_id] += 1
    rng = random.Random(seed)
    return max(experts, key=lambda e: rng.betavariate(wins[e], losses[e]))


class BanditForecaster:
    """`bandit_hedge`: blends the other forecasters' forecasts of the same question."""

    forecaster_id = "bandit_hedge"
    needs_peers = True  # the morning job passes `ctx["peer_forecasts"]`

    def __init__(self, model: HedgeModel) -> None:
        self.model = model

    def version(self) -> str:
        """Algorithm, loss and experts (SPEC 8.5); the learned weights are data, in the meta."""
        return f"hedge-r{REVISION}|brier|{'+'.join(self.model.experts)}"

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        peers: Mapping[str, float] = ctx.get("peer_forecasts", {})
        usable = {e: p for e, p in peers.items() if e in self.model.experts}
        if len(usable) < 2:
            return Skip(
                question_id=q.question_id,
                forecaster_id=self.forecaster_id,
                forecaster_version=self.version(),
                reason_code="model_missing",
                detail=f"{len(usable)} expert forecast(s) for this question; at least 2 needed",
                created_at=asof,
            )
        p, w = self.model.predict(q.domain, usable)
        return Forecast(
            forecast_id=f"{q.question_id}::{self.forecaster_id}",
            question_id=q.question_id,
            forecaster_id=self.forecaster_id,
            forecaster_version=self.version(),
            probability=p,
            created_at=asof,
            meta={
                "weights": {e: round(v, 4) for e, v in w.items()},
                "rounds": self.model.rounds.get(q.domain, 0),
                "experimental": True,
            },
        )
