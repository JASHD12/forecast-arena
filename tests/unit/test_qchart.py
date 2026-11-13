"""Question page data chart (T131): one fixture context per domain."""

from datetime import date

from factories import question

from arena.site.qchart import chart_data, series_svg

DAYS = [f"2026-11-{d:02d}" for d in range(5, 12)]


def q_for(domain: str, template: str, **params):
    q = question(template=template)
    return q.model_copy(update={"domain": domain, "params": {**q.params, **params},
                                "target_date": date(2026, 11, 13)})  # fmt: skip


def check(cd, n_series=1, ref=True, observed=True):
    assert cd is not None and len(cd.series) == n_series
    assert all(len(pts) == len(DAYS) for _, pts in cd.series)
    assert (cd.reference is not None) == ref and (cd.observed is not None) == observed
    svg = str(series_svg(cd))
    assert svg.startswith("<svg") and 'role="img"' in svg and "<desc" in svg
    assert ("ref-line" in svg) == ref and ("qobs" in svg) == observed
    return svg


def test_power() -> None:
    ctx = {"daily": [{"day": d, "mean": 80 + i, "max": 120 + i} for i, d in enumerate(DAYS)]}
    cd = chart_data(q_for("power", "max_gt", stat="max"), ctx, 131.0)
    svg = check(cd)
    assert cd.series[0][0] == "max" and "observed on 2026-11-13" in svg


def test_weather_single_and_duel() -> None:
    rows = [{"day": d, "tmax": 10 + i, "precip": 0.0, "tmin": 2.0} for i, d in enumerate(DAYS)]
    cd = chart_data(q_for("weather", "tmax_gt"), {"observed_daily": rows, "station": "X"}, 14.2)
    check(cd)
    duel = chart_data(q_for("weather", "warmer_than", city_a="Berlin", city_b="Munich"),
                      {"city_a": {"observed_daily": rows}, "city_b": {"observed_daily": rows}},
                      1.0)  # fmt: skip
    check(duel, n_series=2, ref=False, observed=False)
    assert [n for n, _ in duel.series] == ["Berlin", "Munich"]


def test_attention_markets_crypto() -> None:
    views = [{"day": d, "views": 1000 * (i + 1)} for i, d in enumerate(DAYS)]
    check(chart_data(q_for("attention", "views_ge"), {"daily_views": views}, 9000.0))
    fx = [{"day": d, "rate": 1.08 + i / 1000} for i, d in enumerate(DAYS)]
    check(chart_data(q_for("markets", "abs_move_gt"), {"fixings": fx}, 0.004), ref=False,
          observed=False)  # fmt: skip
    px = [{"day": d, "price": 60000.0 + i} for i, d in enumerate(DAYS)]
    check(chart_data(q_for("crypto", "up"), {"daily_usd_00utc": px}, None), ref=False,
          observed=False)  # fmt: skip


def test_missing_values_and_unknown_domains() -> None:
    ctx = {"daily": [{"day": d, "mean": None if i == 2 else 80.0} for i, d in enumerate(DAYS)]}
    cd = chart_data(q_for("power", "mean_gt", stat="mean"), ctx, None)
    assert cd is not None and len(cd.series[0][1]) == len(DAYS) - 1  # nulls are skipped
    assert chart_data(q_for("toy", "x"), {}, None) is None
