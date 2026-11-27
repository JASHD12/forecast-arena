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
    assert S.VERSION == "sentiment-gdelt-r1"
    assert S.SentimentForecaster({}).version() == "sentiment-gdelt-r1"


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
