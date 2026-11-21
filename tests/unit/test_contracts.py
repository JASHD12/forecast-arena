"""T276: data contracts on stored contexts: what they catch and that they never fail a run."""

import gzip
import json
from datetime import date
from types import SimpleNamespace as NS

from arena.ledger import Ledger, layout
from arena.ops import contracts as c

DAY = date(2026, 11, 20)


def power_ctx(**kw):
    ctx = {"domain": "power", "asof": "2026-11-20T07:00:00+00:00", "daily": [{}] * 28,
           "latest_hourly": [100.0] * 24, "latest_day": "2026-11-19"}  # fmt: skip
    return {**ctx, **kw}


def test_a_good_context_passes_and_each_defect_is_named() -> None:
    assert c.check_context("power", power_ctx(), DAY) == []
    bad = c.check_context("power", power_ctx(daily=[{}] * 10), DAY)
    assert bad == ["10 daily rows, expected 28"]
    assert (
        "outside the plausible range"
        in c.check_context("power", power_ctx(latest_hourly=[100.0] * 23 + [9999.0]), DAY)[0]
    )
    assert "stale" in c.check_context("power", power_ctx(latest_day="2026-11-10"), DAY)[0]
    assert "domain field" in c.check_context("weather", power_ctx(), DAY)[0]
    nan = c.check_context("power", power_ctx(latest_hourly=[float("nan")] * 24), DAY)
    assert "plausible" in nan[0]


def test_two_city_weather_contexts_are_checked_per_city() -> None:
    city = {"forecast_daily": {"tmax": 6.9}, "observed_daily": [{}] * 14}
    ok = {"domain": "weather", "asof": "x", "city_a": city, "city_b": city}
    assert c.check_context("weather", ok, DAY) == []
    thin = {**ok, "city_b": {**city, "observed_daily": [{}] * 3}}
    assert c.check_context("weather", thin, DAY) == ["fewer than 10 observed days"]
    hot = {
        "domain": "weather",
        "asof": "x",
        "forecast_daily": {"tmax": 99},
        "observed_daily": [{}] * 14,
    }
    assert "implausible" in c.check_context("weather", hot, DAY)[0]


def test_attention_and_markets_expectations() -> None:
    base = {"domain": "attention", "asof": "x"}
    assert c.check_context("attention", {**base, "daily_views": [{}] * 31}, DAY) == []
    assert "5 days" in c.check_context("attention", {**base, "daily_views": [{}] * 5}, DAY)[0]
    m = {"domain": "markets", "asof": "x", "fixings": [{}] * 60}
    assert c.check_context("markets", m, DAY) == []
    assert "fixings" in c.check_context("markets", {**m, "fixings": [{}] * 5}, DAY)[0]


def test_check_batch_reports_missing_contexts_and_counts(tmp_path) -> None:
    led = Ledger(tmp_path)
    q = lambda qid, dom: NS(question_id=qid, domain=dom, batch_date=DAY)  # noqa: E731
    rec = NS(questions={"a": q("a", "power"), "b": q("b", "power"), "c": q("c", "markets")})
    path = led.abspath(f"{layout.snapshot_dir('power', DAY)}/morning_context.json.gz")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(json.dumps({"a": power_ctx(daily=[])}).encode()))
    checked, bad = c.check_batch(led, rec, DAY)
    assert checked == 1
    assert any(x.startswith("power a: 0 daily rows") for x in bad)
    assert "power b: no stored context" in bad and "markets c: no stored context" in bad
    assert c.check_batch(led, NS(questions={}), DAY) == (0, [])
