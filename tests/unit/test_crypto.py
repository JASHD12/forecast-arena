from datetime import UTC, date, datetime, time, timedelta

import pytest
from crypto_fixtures import fixture_crypto, raw

from arena.config import Settings
from arena.domains.base import AsOfStore
from arena.domains.crypto import COINS, GRACE, CryptoDomain, add_prices, logret
from arena.forecasters.ml_crypto import CryptoModel
from arena.models import Resolution, Void, canonical_json
from arena.site.titles import plain_title
from arena.sources.coingecko import CoinGeckoError, available_at, parse_daily

B = date(2026, 11, 10)
MORNING = datetime.combine(B, time(5, 30), tzinfo=UTC)


def gen(b: date = B):
    return fixture_crypto().generate_questions(b, datetime.combine(b, time(5, 30), tzinfo=UTC))


def test_parser_keeps_only_midnight_points() -> None:
    px = parse_daily(raw("bitcoin"))
    assert len(px) == 365 and min(px) == date(2025, 11, 13) and max(px) == date(2026, 11, 12)
    with pytest.raises(CoinGeckoError):
        parse_daily({"prices": [[1700006400000, -1]]})  # 2023-11-15 00:00 UTC
    with pytest.raises(CoinGeckoError):
        parse_daily({"nope": []})
    assert available_at(date(2026, 11, 12)) == datetime(2026, 11, 12, 1, tzinfo=UTC)


def test_two_templates_per_coin_and_deterministic() -> None:
    qs = gen()
    assert len(qs) == 2 * len(COINS)
    assert {q.template for q in qs} == {"up", "bigmove"}
    assert [canonical_json(q) for q in qs] == [canonical_json(q) for q in gen()]
    for q in qs:
        assert q.target_date == B + timedelta(days=1)
        assert q.lock_time == datetime(2026, 11, 10, 9, 30, tzinfo=UTC)
        assert q.resolve_after == datetime(2026, 11, 12, 1, tzinfo=UTC)
        assert "CoinGecko" in q.text and "revis" in q.resolution_rule
        if q.template == "bigmove":
            assert q.threshold is not None and round(q.threshold, 3) == q.threshold > 0


def test_no_leakage_window_ends_before_batch_morning() -> None:
    dom = fixture_crypto()
    px = dom.prices("bitcoin", MORNING)
    assert max(px) == B  # the 00:00 UTC point of B is known by 05:30 (available 01:00)
    early = dom.prices("bitcoin", datetime.combine(B, time(0, 30), tzinfo=UTC))
    assert max(early) == B - timedelta(days=1)
    q = next(q for q in gen() if q.template == "up")
    ctx = dom.context(q, MORNING)
    assert ctx["daily_usd_00utc"][-1]["day"] == B.isoformat() and len(ctx["daily_usd_00utc"]) == 60


def test_resolution_up_and_bigmove() -> None:
    dom = fixture_crypto()
    for q in gen():
        assert dom.resolve(q, q.resolve_after - timedelta(minutes=1)) is None
        r = dom.resolve(q, q.resolve_after)
        assert isinstance(r, Resolution)
        v = r.evidence.values_used
        assert v["log_return"] == logret(v["p0"], v["p1"])
        if q.template == "up":
            assert r.outcome == int(v["log_return"] > 0)
        else:
            assert r.outcome == int(abs(v["log_return"]) > q.threshold)
        assert r.evidence.source_url.startswith("fixture://")
        assert not dom.revised(q, r)


def test_tie_is_no_missing_waits_then_voids_and_revision_detected() -> None:
    q = next(q for q in gen() if q.template == "up")
    d0, d1 = q.target_date, q.target_date + timedelta(days=1)
    store = AsOfStore()
    add_prices(store, {"bitcoin": {d0: 100.0, d1: 100.0}})
    flat = CryptoDomain(store)
    r = flat.resolve(q, q.resolve_after)
    assert isinstance(r, Resolution) and r.outcome == 0
    empty = CryptoDomain(AsOfStore())
    assert empty.resolve(q, q.resolve_after) is None
    v = empty.resolve(q, q.resolve_after + GRACE)
    assert isinstance(v, Void) and v.reason_code == "source_missing"
    add_prices(store, {"bitcoin": {d1: 101.0}})  # a later revision of P1
    assert flat.revised(q, r)


def test_model_probabilities() -> None:
    dom, m = fixture_crypto(), CryptoModel()
    for q in gen():
        p = m.probability(q, dom.context(q, MORNING))
        assert 0 < p < 1
        if q.template == "up":
            assert p == 0.5
    q = next(q for q in gen() if q.template == "bigmove")
    with pytest.raises(ValueError):
        m.probability(q, {"daily_usd_00utc": []})


def test_titles() -> None:
    by = {(q.template, q.entity): q for q in gen()}
    assert plain_title(by[("up", "bitcoin")]) == "Will Bitcoin end the day higher on Wed 11 Nov?"
    t = plain_title(by[("bigmove", "ripple")])
    assert t.startswith("Will XRP move more than ") and t.endswith("% on Wed 11 Nov?")


def test_live_wiring_skips_without_key() -> None:
    from arena.ops.wiring import build_domains

    skips: list[str] = []
    s = Settings.from_env({"ARENA_DOMAINS": "crypto"})
    assert build_domains(s, MORNING, on_skip=skips.append) == []
    assert skips == ["crypto: ARENA_COINGECKO_API_KEY is not set"]


def test_key_is_sent_as_header_never_in_url() -> None:
    from arena.sources.coingecko import KEY_HEADER, CoinGeckoClient
    from arena.sources.http import HttpClient, HttpResponse

    seen = []

    def transport(req):
        seen.append(req)
        import json

        return HttpResponse(req.url, 200, {}, json.dumps(raw("bitcoin")).encode())

    c = CoinGeckoClient(HttpClient("ua", transport=transport), api_key="k-123")
    got = c.daily("bitcoin")
    assert seen[0].headers[KEY_HEADER] == "k-123" and "k-123" not in seen[0].url
    assert "k-123" not in got.url and len(got.prices) == 365


def test_site_credits_coingecko_only_with_crypto_questions(tmp_path) -> None:
    from arena.clock import FixedClock
    from arena.ledger import Ledger, layout
    from arena.site.build import build_site

    clock = FixedClock(datetime(2026, 11, 11, tzinfo=UTC))
    led = Ledger(tmp_path / "l")
    plain = build_site(led, tmp_path / "s0", clock, tmp_path / "none")
    assert "CoinGecko" not in (plain.out_dir / "index.html").read_text()
    q = gen()[0]
    led.append(layout.questions_path(q.batch_date), [q])
    res = build_site(led, tmp_path / "s1", clock, tmp_path / "none")
    home = (res.out_dir / "index.html").read_text()
    assert '<a href="https://www.coingecko.com">Data provided by CoinGecko</a>' in home
    assert "Crypto" in home
