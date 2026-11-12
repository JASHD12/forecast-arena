"""History from replaying past data through the real question and resolver code (SPEC 8.1).

Before the live record is long enough, `base_rate` and `persistence` need past instances.
They are produced by calling the domain's own `generate_questions` for past batch dates
(each with the as-of time of that morning) and its own `resolve`. Only instances whose
outcome was resolvable before the forecast's `asof` are returned (no leakage).
Limitation: the replay resolves against the values as currently stored; a later SMARD
revision of an old value is therefore reflected in the replayed outcome.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta

from arena.domains.base import Domain
from arena.forecasters.base import History, Instance
from arena.models import Resolution

REPLAY_MORNING = time(5, 30)

Key = tuple[str, str, str]


class ReplayHistory:
    """Replayed instances of one domain, computed once per forecast morning and cached."""

    def __init__(self, domain: Domain, days: int = 200) -> None:
        self.domain = domain
        self.days = days
        self._cache: dict[date, dict[Key, list[Instance]]] = {}

    def _replay(self, asof: datetime) -> dict[Key, list[Instance]]:
        today = asof.date()
        if today in self._cache:
            return self._cache[today]
        out: dict[Key, dict[date, Instance]] = {}
        for back in range(self.days, 0, -1):
            b = today - timedelta(days=back)
            morning = datetime.combine(b, REPLAY_MORNING, tzinfo=UTC)
            for q in self.domain.generate_questions(b, morning):
                if q.resolve_after > asof:
                    continue
                r = self.domain.resolve(q, asof)
                if isinstance(r, Resolution):
                    key = (q.domain, q.template, q.entity)
                    out.setdefault(key, {})[q.target_date] = Instance(q.target_date, r.outcome)
        result = {k: [v[d] for d in sorted(v)] for k, v in out.items()}
        self._cache = {today: result}  # keep one morning only
        return result

    def instances(
        self, domain: str, template: str, entity: str, before: date, asof: datetime
    ) -> Sequence[Instance]:
        """See `History.instances`."""
        if domain != self.domain.name:
            return []
        rows = self._replay(asof).get((domain, template, entity), [])
        return [i for i in rows if i.target_date < before]


class CombinedHistory:
    """Live ledger instances first; replayed instances fill dates the ledger lacks."""

    def __init__(self, primary: History, fallbacks: Sequence[History]) -> None:
        self.primary = primary
        self.fallbacks = list(fallbacks)

    def instances(
        self, domain: str, template: str, entity: str, before: date, asof: datetime
    ) -> Sequence[Instance]:
        """See `History.instances`."""
        by_day = {}
        for h in reversed(self.fallbacks):
            for i in h.instances(domain, template, entity, before, asof):
                by_day[i.target_date] = i
        for i in self.primary.instances(domain, template, entity, before, asof):
            by_day[i.target_date] = i
        return [by_day[d] for d in sorted(by_day)]
