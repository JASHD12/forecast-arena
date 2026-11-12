from datetime import UTC, date, datetime

import pytest
from weather_fixtures import fixture_weather

from arena.forecasters.ml import MLForecaster
from arena.forecasters.ml_weather import WeatherRules, normal_sf
from arena.models import Forecast, Skip

LATE = datetime(2026, 11, 12, 11, 30, tzinfo=UTC)  # after the fixture forecast was fetched


def test_probabilities_for_both_templates() -> None:
    dom = fixture_weather()
    qs = dom.generate_questions(date(2026, 11, 12), datetime(2026, 11, 12, 5, 30, tzinfo=UTC))
    f = MLForecaster({"weather": WeatherRules()})
    seen = set()
    for q in qs:
        out = f.forecast(q, dom.context(q, LATE), LATE)
        assert isinstance(out, Forecast) and 0 < out.probability < 1
        assert out.forecaster_version == "weather-rules-r1"
        seen.add(q.template)
    assert seen == {"tmax_gt", "wet_day"}


def test_rules() -> None:
    assert normal_sf(0) == pytest.approx(0.5)
    r = WeatherRules()

    class Q:
        def __init__(self, template, threshold=None):
            self.template, self.threshold = template, threshold

    assert r.probability(Q("tmax_gt", 10.0), {"forecast_daily": {"tmax": 10.0}}) == 0.5
    assert r.probability(Q("tmax_gt", 10.0), {"forecast_daily": {"tmax": 14.0}}) > 0.97
    assert r.probability(Q("wet_day", 1.0), {"forecast_daily": {"precip": 0.0}}) == 0.10
    assert r.probability(Q("wet_day", 1.0), {"forecast_daily": {"precip": 5.0}}) == 0.90


def test_no_forecast_is_a_skip_not_a_guess() -> None:
    dom = fixture_weather()
    q = dom.generate_questions(date(2026, 11, 12), datetime(2026, 11, 12, 5, 30, tzinfo=UTC))[0]
    early = datetime(2026, 11, 12, 5, 30, tzinfo=UTC)  # forecast not fetched yet
    out = MLForecaster({"weather": WeatherRules()}).forecast(q, dom.context(q, early), early)
    assert isinstance(out, Skip) and out.reason_code == "error"
