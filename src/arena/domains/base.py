"""Domain contract (SPEC 7.0), as-of gateway, degeneracy rule and registry."""

from __future__ import annotations

import bisect
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from arena.clock import ensure_utc
from arena.models import Question, Resolution, Void

DEGENERACY_LOW = 0.10
DEGENERACY_HIGH = 0.90


class Domain(Protocol):
    """A family of questions sharing data sources."""

    name: str

    def generate_questions(self, batch_date: date, asof: datetime) -> list[Question]:
        """Deterministic questions for a batch, using only data available at `asof`."""
        ...

    def context(self, question: Question, asof: datetime) -> dict[str, Any]:
        """Everything a forecaster may see; built only through the as-of gateway."""
        ...

    def resolve(self, question: Question, now: datetime) -> Resolution | Void | None:
        """None until resolvable; a Void after grace without data; else a Resolution."""
        ...


@dataclass(frozen=True, order=True)
class Observation:
    """One value of a series. `available_at` is when it could first have been known."""

    available_at: datetime
    observed_at: datetime
    key: str
    value: float | None


class AsOfStore:
    """Series values indexed by availability time. The only data path to forecasters."""

    def __init__(self, observations: Iterable[Observation] = ()) -> None:
        self._by_key: dict[str, list[Observation]] = {}
        for obs in observations:
            self.add(obs)

    def add(self, obs: Observation) -> None:
        """Insert an observation (times must be timezone-aware)."""
        ensure_utc(obs.available_at)
        ensure_utc(obs.observed_at)
        bisect.insort(self._by_key.setdefault(obs.key, []), obs)

    def keys(self) -> list[str]:
        """Known series keys."""
        return sorted(self._by_key)

    def series(
        self, key: str, asof: datetime, lookback: timedelta | None = None
    ) -> list[Observation]:
        """Observations of `key` available at or before `asof`, ordered by observation time.

        If a value was revised, only the latest version available at `asof` is returned.
        `lookback` limits by observation time relative to `asof`.
        """
        asof = ensure_utc(asof)
        rows = self._by_key.get(key, [])
        cut = bisect.bisect_right([o.available_at for o in rows], asof)
        latest: dict[datetime, Observation] = {}
        for obs in rows[:cut]:
            latest[obs.observed_at] = obs  # later availability overwrites earlier versions
        out = sorted(latest.values(), key=lambda o: o.observed_at)
        if lookback is not None:
            out = [o for o in out if o.observed_at >= asof - lookback]
        return out


def trailing_frequency(outcomes: Sequence[int]) -> float | None:
    """Empirical YES frequency, or None with no history."""
    return sum(outcomes) / len(outcomes) if outcomes else None


def is_degenerate(freq: float | None) -> bool:
    """SPEC 7.0: skip a template when its trailing YES frequency is outside [0.10, 0.90].

    With no history at all the rule cannot be applied and the template is kept.
    """
    if freq is None:
        return False
    return not (DEGENERACY_LOW <= freq <= DEGENERACY_HIGH)


class DomainRegistry:
    """Name -> domain instance."""

    def __init__(self) -> None:
        self._domains: dict[str, Domain] = {}

    def register(self, domain: Domain) -> None:
        """Add a domain; names are unique."""
        if domain.name in self._domains:
            raise ValueError(f"domain {domain.name!r} already registered")
        self._domains[domain.name] = domain

    def get(self, name: str) -> Domain:
        """Look a domain up by name."""
        try:
            return self._domains[name]
        except KeyError:
            raise KeyError(f"unknown domain {name!r}") from None

    def enabled(self, names: Sequence[str]) -> list[Domain]:
        """The domains named in settings, in that order."""
        return [self.get(n) for n in names]
