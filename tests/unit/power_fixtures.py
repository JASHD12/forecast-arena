"""Power domain built from recorded SMARD fixtures."""

from datetime import date

from smard_fixtures import fixture_client

from arena.domains.power import PowerDomain
from arena.domains.power_history import PRICE_KEY, PowerHistory

FIRST, LAST = date(2025, 10, 13), date(2026, 11, 15)


def fixture_domain(skips: list[str] | None = None) -> PowerDomain:
    client, _ = fixture_client()
    store = PowerHistory(client).store([PRICE_KEY], FIRST, LAST)
    return PowerDomain(store, on_skip=(skips.append if skips is not None else None))
