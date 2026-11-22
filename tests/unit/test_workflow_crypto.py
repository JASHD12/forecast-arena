"""T045e: the CoinGecko key reaches exactly the three jobs that need prices, and crypto is a default topic."""

from __future__ import annotations

from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
NEEDS_PRICES = {"morning.yml", "evening.yml", "resolve.yml"}


def test_secret_is_passed_only_to_the_price_jobs() -> None:
    users = {
        p.name for p in WORKFLOWS.glob("*.yml") if "ARENA_COINGECKO_API_KEY" in p.read_text("utf-8")
    }
    assert users == NEEDS_PRICES


def test_secret_goes_only_into_an_environment_variable() -> None:
    for name in NEEDS_PRICES:
        lines = [
            line
            for line in (WORKFLOWS / name).read_text("utf-8").splitlines()
            if "secrets.ARENA_COINGECKO_API_KEY" in line
        ]
        assert len(lines) == 1
        assert lines[0].strip().startswith("ARENA_COINGECKO_API_KEY: ${{ secrets.")


def test_crypto_is_in_the_default_domains() -> None:
    for name in NEEDS_PRICES:
        text = (WORKFLOWS / name).read_text("utf-8")
        assert "'power,weather,attention,markets,crypto'" in text
