"""German nationwide public holidays (used as a calendar feature by the power model).

Nationwide holidays by federal and state law: New Year's Day, Good Friday, Easter Monday,
Labour Day (1 May), Ascension Day, Whit Monday, Day of German Unity (3 October),
Christmas Day and 26 December. Regional holidays are ignored. Source: statutory list;
not checked against an online page in this session (see docs/SOURCES.md).
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

from arena.sources.ecb import easter


@lru_cache(maxsize=64)
def national_holidays(year: int) -> frozenset[date]:
    """The nationwide public holidays of a year."""
    e = easter(year)
    return frozenset({
        date(year, 1, 1), e - timedelta(days=2), e + timedelta(days=1), date(year, 5, 1),
        e + timedelta(days=39), e + timedelta(days=50), date(year, 10, 3),
        date(year, 12, 25), date(year, 12, 26),
    })  # fmt: skip


def is_holiday(d: date) -> bool:
    """True on a nationwide German public holiday."""
    return d in national_holidays(d.year)
