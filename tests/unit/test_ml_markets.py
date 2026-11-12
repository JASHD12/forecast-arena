import gzip
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest

from arena.domains.markets import markets_domain_from_rates
from arena.forecasters.ml import MLForecaster
from arena.forecasters.ml_markets import MarketsModel, ewma_daily_variance, weekdays_between
from arena.models import Forecast
from arena.sources.ecb import parse_csv

FIX = Path(__file__).parents[1] / "fixtures" / "ecb" / "exr_usd_jpy_2019-01-01.csv.gz"
RATES = parse_csv(gzip.decompress(FIX.read_bytes()).decode())


def test_weekdays_between() -> None:
    assert weekdays_between(date(2026, 11, 6), date(2026, 11, 9)) == 1  # Fri -> Mon
    assert weekdays_between(date(2026, 4, 2), date(2026, 4, 7)) == 3  # Easter
    assert weekdays_between(date(2026, 11, 9), date(2026, 11, 10)) == 1


def test_ewma_variance_and_probabilities() -> None:
    flat = [(date(2026, 1, d), 1.0 + 0.001 * (d % 2)) for d in range(5, 10)]
    assert ewma_daily_variance(flat) > 0
    dom = markets_domain_from_rates(RATES, "fixture://ecb", "e" * 64)
    b = date(2026, 11, 6)
    asof = datetime.combine(b, time(5, 30), tzinfo=UTC)
    f = MLForecaster({"markets": MarketsModel()})
    for q in dom.generate_questions(b, asof):
        out = f.forecast(q, dom.context(q, asof), asof)
        assert isinstance(out, Forecast)
        if q.template == "up":
            assert out.probability == 0.5
        else:
            assert 0.05 < out.probability < 0.95


def test_bigger_threshold_lower_probability() -> None:
    dom = markets_domain_from_rates(RATES, "fixture://ecb", "e" * 64)
    b = date(2026, 11, 6)
    asof = datetime.combine(b, time(5, 30), tzinfo=UTC)
    q = next(q for q in dom.generate_questions(b, asof) if q.template == "absmove_gt")
    ctx = dom.context(q, asof)
    m = MarketsModel()
    ps = [m.probability(q.model_copy(update={"threshold": t}), ctx) for t in (0.001, 0.003, 0.01)]
    assert ps == sorted(ps, reverse=True)
    with pytest.raises(ValueError):
        m.probability(q, {"fixings": []})
