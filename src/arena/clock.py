"""Injectable time source. Library code never calls `datetime.now()` directly."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """Anything that can say what time it is (always timezone-aware UTC)."""

    def now(self) -> datetime:
        """Return the current time as an aware UTC datetime."""
        ...


def ensure_utc(value: datetime) -> datetime:
    """Return `value` converted to UTC; refuse naive datetimes."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"naive datetime not allowed: {value!r}")
    return value.astimezone(UTC)


class SystemClock:
    """The real wall clock."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        return datetime.now(UTC)


class FixedClock:
    """A clock frozen at a given instant; `advance()` moves it forward (tests, e2e)."""

    def __init__(self, at: datetime) -> None:
        self._at = ensure_utc(at)

    def now(self) -> datetime:
        """Return the frozen instant."""
        return self._at

    def set(self, at: datetime) -> None:
        """Jump to a new instant."""
        self._at = ensure_utc(at)

    def advance(self, delta: timedelta) -> None:
        """Move the clock forward by `delta` (negative deltas are refused)."""
        if delta < timedelta(0):
            raise ValueError("a clock never goes backwards")
        self._at = self._at + delta
