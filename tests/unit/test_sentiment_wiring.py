"""GDELT aggregates in the crypto morning context (T373): off by default, no effect on others."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from pathlib import Path

from crypto_fixtures import fixture_crypto

from arena.config import Settings
from arena.domains.crypto import COINS
from arena.forecasters.llm import render_context
from arena.ops.wiring import gdelt_news
from arena.sources.http import HttpClient, HttpRequest, HttpResponse

FIX = Path(__file__).parents[1] / "fixtures" / "gdelt"
B = date(2026, 11, 10)
ASOF = datetime.combine(B, time(5, 30), tzinfo=UTC)


def test_flag_is_off_by_default_and_parses() -> None:
    assert Settings.from_env({}).sentiment is False
    assert Settings.from_env({"ARENA_SENTIMENT": "1"}).sentiment is True


def test_context_has_no_gdelt_unless_a_provider_is_set() -> None:
    dom = fixture_crypto()
    q = dom.generate_questions(B, ASOF)[0]
    assert "gdelt" not in dom.context(q, ASOF)
    dom.news = lambda coin, asof: {"last_known_day": "2026-11-08", "tone": [], "count": []}
    assert dom.context(q, ASOF)["gdelt"]["last_known_day"] == "2026-11-08"
    dom.news = lambda coin, asof: None
    assert "gdelt" not in dom.context(q, ASOF)


def test_other_forecasters_never_see_the_gdelt_numbers() -> None:
    base = {"coin": "Bitcoin", "daily_usd_00utc": [{"day": "2026-11-09", "price": 1.0}]}
    assert render_context({**base, "gdelt": {"tone": [["2026-11-08", -1.0]]}}) == render_context(
        base
    )


def _transport(fail: bool):  # type: ignore[no-untyped-def]
    def go(req: HttpRequest) -> HttpResponse:
        if fail:
            return HttpResponse(req.url, 404, {}, b"")
        name = "bitcoin_timelinetone_20261101_20261110.json"
        if "TimelineVolRaw" in req.url:
            name = "bitcoin_timelinevolraw_20261101_20261110.json"
        return HttpResponse(req.url, 200, {}, (FIX / name).read_bytes())

    return go


def test_gdelt_news_provider_keeps_only_known_days() -> None:
    http = HttpClient("test-agent", transport=_transport(False), sleep=lambda s: None)
    skips: list[str] = []
    provider = gdelt_news(http, datetime(2026, 11, 10, 5, 30, tzinfo=UTC), skips.append, pause=0)
    ctx = provider("bitcoin", ASOF)
    assert ctx is not None and ctx["last_known_day"] == "2026-11-08"
    assert max(d for d, _ in ctx["tone"]) == "2026-11-08"  # 9 and 10 Nov are not known yet
    assert skips == []


def test_gdelt_failure_is_a_recorded_skip_and_no_context() -> None:
    http = HttpClient("test-agent", transport=_transport(True), retries=0, sleep=lambda s: None)
    skips: list[str] = []
    provider = gdelt_news(http, ASOF, skips.append, pause=0)
    assert provider("bitcoin", ASOF) is None
    assert len(skips) == len(COINS) and skips[0].startswith("crypto/gdelt/")
