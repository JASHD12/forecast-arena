"""Crypto domain built from recorded CoinGecko fixtures."""

import gzip
import json
from pathlib import Path

from arena.domains.crypto import COINS, CryptoDomain, crypto_domain_from_prices
from arena.sources.coingecko import parse_daily

FIXTURES = Path(__file__).parents[1] / "fixtures" / "coingecko"


def raw(coin: str) -> dict:
    return json.loads(gzip.decompress((FIXTURES / f"{coin}_365d.json.gz").read_bytes()))


def fixture_crypto(skips: list[str] | None = None) -> CryptoDomain:
    prices = {c: parse_daily(raw(c)) for c in COINS}
    return crypto_domain_from_prices(
        prices,
        {c: (f"fixture://{c}", "c" * 64) for c in COINS},
        on_skip=(skips.append if skips is not None else None),
    )
