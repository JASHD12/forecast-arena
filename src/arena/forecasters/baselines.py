"""`base_rate` (SPEC 8.1) and `persistence` (SPEC 8.2)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from arena.forecasters.base import History, Instance
from arena.models import Forecast, Question, Skip

MIN_INSTANCES = 10


def laplace(yes: int, n: int) -> float:
    """Laplace-smoothed frequency (yes + 1) / (n + 2)."""
    return (yes + 1) / (n + 2)


def _forecast(
    fid: str, version: str, q: Question, p: float, asof: datetime, **meta: Any
) -> Forecast:
    return Forecast(
        forecast_id=f"{q.question_id}::{fid}",
        question_id=q.question_id,
        forecaster_id=fid,
        forecaster_version=version,
        probability=p,
        created_at=asof,
        meta=meta,
    )


class BaseRate:
    """Laplace-smoothed YES frequency over the latest 90 resolved instances; 0.5 below 10."""

    forecaster_id = "base_rate"
    window = 90

    def __init__(self, history: History) -> None:
        self.history = history

    def version(self) -> str:
        """Rule version."""
        return "1"

    def probability(self, q: Question, asof: datetime) -> tuple[float, int]:
        """(probability, number of instances used)."""
        past = list(self.history.instances(q.domain, q.template, q.entity, q.target_date, asof))
        recent = past[-self.window :]
        if len(recent) < MIN_INSTANCES:
            return 0.5, len(recent)
        return laplace(sum(i.outcome for i in recent), len(recent)), len(recent)

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        p, n = self.probability(q, asof)
        return _forecast(self.forecaster_id, self.version(), q, p, asof, instances=n,
                         rule="laplace" if n >= MIN_INSTANCES else "fewer_than_10")  # fmt: skip


class Persistence:
    """P(YES | yesterday's outcome) over 180 instances, smoothed; else the base rate."""

    forecaster_id = "persistence"
    window = 180

    def __init__(self, history: History) -> None:
        self.history = history
        self.base = BaseRate(history)

    def version(self) -> str:
        """Rule version."""
        return "1"

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Forecast | Skip:
        """See `Forecaster.forecast`."""
        past = list(self.history.instances(q.domain, q.template, q.entity, q.target_date, asof))
        by_day = {i.target_date: i.outcome for i in past}
        yesterday = by_day.get(q.target_date - timedelta(days=1))
        if yesterday is None:
            p, n = self.base.probability(q, asof)
            return _forecast(self.forecaster_id, self.version(), q, p, asof,
                             fallback="yesterday_unknown", instances=n)  # fmt: skip
        pairs = _transitions(past[-self.window :])
        after = [today for prev, today in pairs if prev == yesterday]
        if len(after) < 10:
            p, n = self.base.probability(q, asof)
            return _forecast(self.forecaster_id, self.version(), q, p, asof,
                             fallback="fewer_than_10_transitions", instances=n)  # fmt: skip
        p = laplace(sum(after), len(after))
        return _forecast(self.forecaster_id, self.version(), q, p, asof,
                         yesterday=yesterday, transitions=len(after))  # fmt: skip


def _transitions(instances: list[Instance]) -> list[tuple[int, int]]:
    """(outcome on t-1, outcome on t) for consecutive target dates."""
    by_day = {i.target_date: i.outcome for i in instances}
    return [(by_day[d - timedelta(days=1)], o) for d, o in by_day.items()
            if d - timedelta(days=1) in by_day]  # fmt: skip
