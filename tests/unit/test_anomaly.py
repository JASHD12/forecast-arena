"""T294: unsupervised anomaly detection on the daily price rows of a context."""

from datetime import date, timedelta

import numpy as np
import pytest

from arena.lab import anomaly_study as st
from arena.ops import anomaly


def rows(n: int = 28, seed: int = 0, last: float | None = None):
    rng = np.random.default_rng(seed)
    out = []
    for d in range(n):
        base = 90 + rng.normal(0, 6)
        r = {
            "day": (date(2026, 10, 1) + timedelta(days=d)).isoformat(),
            "mean": base,
            "max": base + 60 + rng.normal(0, 5),
            "min": base - 55 + rng.normal(0, 5),
            "spread": 115 + rng.normal(0, 8),
            "evening": base + 30 + rng.normal(0, 5),
        }
        out.append(r)
    if last is not None:
        out[-1] = {
            **out[-1],
            "mean": last,
            "max": last * 2,
            "min": last * 0.2,
            "spread": last * 1.8,
            "evening": last * 1.5,
        }
    return out


def test_a_normal_day_is_not_flagged_and_a_wild_one_is() -> None:
    ok = anomaly.check_rows(rows())
    bad = anomaly.check_rows(rows(last=2000.0))
    assert not ok["isolation_flag"] and not ok["robust_z_flag"]
    assert bad["robust_z_flag"] and bad["isolation_score"] > ok["isolation_score"]
    # with only 27 fitting points the forest stays close to its threshold even for a wild day:
    # the lab study measures exactly this (robust z catches more injected faults)


def test_scores_are_deterministic_and_need_enough_rows() -> None:
    r = rows()
    assert anomaly.isolation_score(r) == anomaly.isolation_score(r)
    with pytest.raises(ValueError, match="need"):
        anomaly.isolation_score(rows(10))


def test_injected_faults_change_the_hourly_prices_as_described() -> None:
    d = date(2026, 10, 5)
    daily = {d - timedelta(days=1): [50.0] * 24, d: [40.0 + i for i in range(24)]}
    assert st.inject("unit_error", daily, d)[0] == pytest.approx(0.04)
    assert len(set(st.inject("flat_feed", daily, d))) == 1
    assert st.inject("repeated_day", daily, d) == [50.0] * 24
    assert max(st.inject("spike", daily, d)) == pytest.approx(63 * 8)
    with pytest.raises(ValueError):
        st.inject("nope", daily, d)


def test_latest_batch_anomaly_reads_the_stored_power_context(tmp_path) -> None:
    import gzip
    import json
    from types import SimpleNamespace as NS

    from arena.ledger import Ledger, layout

    day = date(2026, 11, 20)
    led = Ledger(tmp_path)
    led.write_raw(
        f"{layout.snapshot_dir('power', day)}/morning_context.json.gz",
        gzip.compress(json.dumps({"power-q1": {"daily": rows()}}).encode()),
    )
    rec = NS(questions={"power-q1": NS(batch_date=day, domain="power", question_id="power-q1")})
    res = anomaly.latest_batch_anomaly(led, rec, day)
    assert res is not None and res["robust_z_flag"] is False and "isolation_score" in res
    assert anomaly.latest_batch_anomaly(led, NS(questions={}), day) is None


def test_regimes_find_two_planted_daily_shapes_and_pinball_is_asymmetric() -> None:
    from arena.lab import regimes as rg

    rng = np.random.default_rng(0)
    solar = [50 - 40 * np.exp(-((h - 13) ** 2) / 8) for h in range(24)]  # midday dip
    flat = [60 + 5 * np.sin(h / 3) for h in range(24)]
    daily = {}
    for i in range(120):
        base = solar if i % 2 else flat
        daily[date(2024, 1, 1) + timedelta(days=i)] = [x + rng.normal(0, 1.5) for x in base]
    km, info = rg.fit_regimes(daily, date(2024, 1, 1), date(2024, 4, 29))
    lab = rg.labels(km, daily)
    assert info["k"] == 2 and len({lab[d] for d in daily}) == 2
    d0, d1 = date(2024, 1, 1), date(2024, 1, 2)
    assert lab[d0] != lab[d1] and lab[d0] == lab[date(2024, 1, 3)]
    y, q = np.array([10.0]), np.array([4.0])
    assert rg.pinball(y, q, 0.9)[0] == pytest.approx(5.4) and rg.pinball(y, q, 0.1)[
        0
    ] == pytest.approx(0.6)
    assert len(rg.profile([1.0] * 23)) == 24 and len(rg.profile([1.0] * 25)) == 24
