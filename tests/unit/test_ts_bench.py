from datetime import date, timedelta

import pytest

from arena.forecasters import ts_bench
from arena.forecasters.ml import MLForecaster
from arena.forecasters.ts_bench import SeriesBenchmark, cdf_from_quantiles, gaussian_cdf

D = date(2026, 6, 1)


def ctx(values: list[float], last: date = D) -> dict:
    days = [last - timedelta(days=len(values) - 1 - i) for i in range(len(values))]
    return {"daily": [{"day": d.isoformat(), "mean": v} for d, v in zip(days, values, strict=True)]}


class Q:
    """Just the question fields `probability` reads."""

    def __init__(self, threshold: float, comparator: str = "gt", template: str = "mean_gt"):
        self.params = {"stat": "mean", "reference_mean": threshold}
        self.threshold, self.comparator, self.template = threshold, comparator, template
        self.target_date = D + timedelta(days=1)


def test_cdf_helpers() -> None:
    lv = (0.1, 0.5, 0.9)
    assert cdf_from_quantiles(lv, [10, 20, 30], 20) == pytest.approx(0.5)
    assert cdf_from_quantiles(lv, [10, 20, 30], 0) == pytest.approx(0.05)  # halved tail
    assert cdf_from_quantiles(lv, [10, 20, 30], 99) == pytest.approx(0.95)
    assert gaussian_cdf(0, 1, 0) == pytest.approx(0.5)
    assert gaussian_cdf(5, 0, 5) == 1.0 and gaussian_cdf(5, 0, 4) == 0.0
    with pytest.raises(ValueError):
        gaussian_cdf(float("nan"), 1, 0)


@pytest.mark.parametrize("method", ["ets", "sarimax"])
def test_statistical_models_follow_the_level(method: str) -> None:
    pytest.importorskip("statsmodels")
    weekly = [0, 4, 6, 5, 3, -2, -8]
    values = [80 + weekly[i % 7] + (i % 3) * 0.5 for i in range(28)]
    m = SeriesBenchmark(method)
    lo, hi = m.probability(Q(40), ctx(values)), m.probability(Q(120), ctx(values))
    assert lo > 0.95 and hi < 0.05  # far below / far above the level
    assert m.probability(Q(40, "lt"), ctx(values)) == pytest.approx(1 - lo)
    assert m.version.startswith("power-") and len(m.model_hash()) == 12


def test_chronos_path_with_a_fake_pipeline(monkeypatch) -> None:
    torch = pytest.importorskip("torch")
    calls = []

    class FakePipe:
        def predict_quantiles(self, series, prediction_length, quantile_levels):
            calls.append((len(series), prediction_length))
            last = float(series[-1])
            q = torch.tensor([[[last + 10 * (lv - 0.5) for lv in quantile_levels]]])
            return q.repeat(1, prediction_length, 1), None

    monkeypatch.setattr(ts_bench, "chronos_pipeline", lambda: FakePipe())
    m = SeriesBenchmark("chronos")
    c = ctx([50.0] * 20)
    assert m.probability(Q(50), c) == pytest.approx(0.5)
    assert m.probability(Q(50), c) == pytest.approx(0.5)
    assert calls == [(20, 1)]  # cached per (stat, series, horizon)


def test_too_little_history_or_bad_horizon_becomes_a_skip() -> None:
    m = SeriesBenchmark("ets")
    f = MLForecaster({"power": m})
    q = Q(50)
    q.domain, q.question_id = "power", "power-x"  # type: ignore[attr-defined]
    from datetime import UTC, datetime

    rec = f.forecast(q, ctx([50.0] * 5), datetime(2026, 6, 1, 5, tzinfo=UTC))  # type: ignore[arg-type]
    assert rec.kind == "skip" and "known days" in rec.detail
    with pytest.raises(ValueError):
        m.cdf("mean", ctx([50.0] * 20, last=D + timedelta(days=1)), D + timedelta(days=1))
    with pytest.raises(ValueError):
        SeriesBenchmark("nope")
