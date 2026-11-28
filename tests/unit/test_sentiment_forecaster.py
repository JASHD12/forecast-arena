"""`sentiment` forecaster (T373): features, as-of context, fitting and recorded skips."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest
from crypto_fixtures import fixture_crypto

from arena.forecasters import sentiment as S
from arena.models import Forecast, Question, Skip

ASOF = datetime(2026, 11, 5, 5, 30, tzinfo=UTC)  # latest known GDELT day: 2026-11-03


def _gdelt(last: date = date(2026, 11, 3), n_prior: int = 7) -> dict:
    tone = [[(last - timedelta(days=i)).isoformat(), -0.5 + 0.1 * i] for i in range(n_prior + 1)]
    count = [[(last - timedelta(days=i)).isoformat(), 10 + i] for i in range(n_prior + 1)]
    return {"last_known_day": last.isoformat(), "tone": tone, "count": count}


def _q(template: str = "bigmove") -> Question:
    b = date(2026, 11, 10)
    qs = fixture_crypto().generate_questions(b, datetime.combine(b, time(5, 30), tzinfo=UTC))
    return next(q for q in qs if q.template == template and q.entity == "bitcoin")


def test_version_is_pinned() -> None:
    assert S.VERSION == "sentiment-gdelt-r2"
    assert S.SentimentForecaster({}).version() == "sentiment-gdelt-r2"


def test_features_bigmove_and_up() -> None:
    vec, why = S.features("bigmove", _gdelt(), 0.6)
    assert why == "" and vec is not None and len(vec) == 4
    assert vec[0] == pytest.approx(-0.5)
    assert vec[3] == pytest.approx(S.logit(0.6))
    up, _ = S.features("up", _gdelt(), None)
    assert up is not None and len(up) == 3


def test_features_skip_reasons_are_recorded_not_guessed() -> None:
    assert S.features("up", None, None)[0] is None
    assert "no news tone" in S.features("up", {**_gdelt(), "tone": []}, None)[1]
    assert "no article count" in S.features("up", {**_gdelt(), "count": []}, None)[1]
    assert "fewer than 4" in S.features("up", _gdelt(n_prior=2), None)[1]
    assert "no ml probability" in S.features("bigmove", _gdelt(), None)[1]


def test_context_uses_only_days_known_at_asof_rule() -> None:
    tone = {date(2026, 11, d): float(d) for d in range(1, 8)}  # days 4..7 are not yet known
    count = {date(2026, 11, d): d for d in range(1, 8)}
    ctx = S.gdelt_context(tone, count, set(count), ASOF)
    assert ctx is not None and ctx["last_known_day"] == "2026-11-03"
    assert max(d for d, _ in ctx["tone"]) == "2026-11-03"
    assert max(d for d, _ in ctx["count"]) == "2026-11-03"
    assert "2026-11-04" not in {d for d, _ in ctx["tone"]}
    assert ctx["source"].startswith("Data: GDELT")


def test_context_distinguishes_zero_articles_from_unrecorded_days() -> None:
    covered = {date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3)}
    ctx = S.gdelt_context({}, {date(2026, 11, 1): 4}, covered, ASOF)
    assert ctx is not None
    assert ["2026-11-02", 0] in ctx["count"]  # recorded range, no articles: zero
    assert "2026-10-30" not in {d for d, _ in ctx["count"]}  # not recorded: unknown
    assert S.gdelt_context({}, {}, set(), ASOF) is None


def test_fit_needs_enough_rows_and_both_classes() -> None:
    x = [[float(i % 5), 0.1, 0.2] for i in range(100)]
    assert S.fit("up", x[:10], [0, 1] * 5) is None
    assert S.fit("up", x, [1] * 100) is None
    m = S.fit("up", x, [i % 2 for i in range(100)])
    assert m is not None and m.n_train == 100
    assert 0.02 <= m.probability([1.0, 0.1, 0.2]) <= 0.98
    with pytest.raises(ValueError):
        S.fit("up", [[1.0, 2.0]] * 100, [0, 1] * 50)
    with pytest.raises(ValueError):
        S.fit("weekly", x, [0, 1] * 50)


def test_forecaster_forecast_and_skips() -> None:
    x = [[float(i % 7) - 3, 0.1 * (i % 3), 0.2, 0.0] for i in range(120)]
    model = S.fit("bigmove", x, [i % 2 for i in range(120)])
    assert model is not None
    f = S.SentimentForecaster({"bigmove": model})
    assert f.needs_peers is True and f.forecaster_id == "sentiment"
    q = _q("bigmove")
    ctx = {"gdelt": _gdelt(), "peer_forecasts": {"ml": 0.4}}
    out = f.forecast(q, ctx, ASOF)
    assert isinstance(out, Forecast) and 0.02 <= out.probability <= 0.98
    assert set(out.meta["features"]) == {"tone", "tone_chg", "vol_chg", "logit_ml"}
    for bad, key in (({"peer_forecasts": {"ml": 0.4}}, "GDELT"), ({"gdelt": _gdelt()}, "ml")):
        sk = f.forecast(q, bad, ASOF)
        assert isinstance(sk, Skip) and sk.reason_code == "model_missing" and key in sk.detail
    other = f.forecast(_q("up"), ctx, ASOF)
    assert isinstance(other, Skip) and "no model" in other.detail


def _days(last: date, n: int) -> list[date]:
    return [last - timedelta(days=i) for i in range(n)]


def test_r2_drops_the_tone_of_a_day_with_no_articles() -> None:
    """GDELT reports value 0 with count 0 for an empty day: not a news tone of 0 (T402)."""
    last = date(2026, 11, 3)
    days = _days(last, 8)
    tone = {d: -0.5 for d in days}
    tone[last] = 0.0  # the empty day: value 0
    count = {d: 12 for d in days}
    count[last] = 0
    r1 = S.gdelt_context(tone, count, set(count), ASOF)
    assert r1 is not None and [last.isoformat(), 0.0] in r1["tone"]  # r1 keeps it
    r2 = S.gdelt_context(tone, count, set(count), ASOF, unknown_days=set())
    assert r2 is not None and last.isoformat() not in {d for d, _ in r2["tone"]}
    assert [last.isoformat(), 0] in r2["count"]  # the count of 0 is still real
    vec, why = S.features("up", r2, None)
    assert vec is None and "no news tone" in why  # the skip that r1 never reached


def test_r2_treats_an_outage_day_as_unknown_not_as_zero_articles() -> None:
    last = date(2026, 11, 3)
    outage = last - timedelta(days=2)
    days = [d for d in _days(last, 8) if d != outage]
    tone = {d: -0.5 for d in days}
    count = {d: 12 for d in days}
    covered = set(_days(last, 8))
    r1 = S.gdelt_context(tone, count, covered, ASOF)
    r2 = S.gdelt_context(tone, count, covered, ASOF, unknown_days={outage})
    assert r1 is not None and r2 is not None
    assert [outage.isoformat(), 0] in r1["count"]  # r1: an outage counts as zero articles
    assert outage.isoformat() not in {d for d, _ in r2["count"]}


def test_outage_days_are_the_covered_days_without_a_count_for_any_coin() -> None:
    d1, d2, d3 = date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)
    counts = {"bitcoin": {d1: 5}, "ethereum": {d1: 2, d2: 1}}
    assert S.outage_days(counts, {d1, d2, d3}) == {d3}  # d2 is quiet for bitcoin only
    assert S.outage_days({}, {d1}) == {d1}


def test_the_morning_provider_passes_the_outage_days(monkeypatch: pytest.MonkeyPatch) -> None:
    from arena.ops import wiring
    from arena.sources.gdelt_tone import DailyNews

    last = date(2026, 11, 3)
    seen: dict = {}

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def daily(self, coin: str, start: date, end: date) -> DailyNews:
            # bitcoin has data on every day but one; the others have none that day either
            days = [d for d in _days(last, 8) if d != last - timedelta(days=1)]
            return DailyNews(coin, {d: -0.5 for d in days}, {d: 9 for d in days}, {}, (), ())

    real = S.gdelt_context

    def spy(*a: object, **k: object) -> object:
        seen.update(k)
        return real(*a, **k)

    monkeypatch.setattr("arena.sources.gdelt_tone.GdeltClient", FakeClient)
    monkeypatch.setattr(S, "gdelt_context", spy)
    provider = wiring.gdelt_news(object(), datetime(2026, 11, 5, 5, 30, tzinfo=UTC), pause=0.0)  # type: ignore[arg-type]
    assert provider("bitcoin", ASOF) is not None
    assert seen["unknown_days"] and isinstance(seen["unknown_days"], set)
