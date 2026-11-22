"""T293: the Hedge forecaster learns only from outcomes known at forecast time."""

from datetime import UTC, date, datetime, timedelta

import pytest
from factories import question

from arena.forecasters import bandit as bd
from arena.models import Forecast, Skip
from arena.scoring.core import Scored

ASOF = datetime(2026, 11, 24, 7, tzinfo=UTC)


def scored(
    expert: str, p: float, y: int, day: date, domain: str = "power", qid: str = ""
) -> Scored:
    return Scored(qid or f"{domain}-{day}-{expert}", expert, "v1", domain, day, p, y)


def history(n_days: int = 20) -> list[Scored]:
    """`good` is right, `bad` is always wrong, on the same questions."""
    rows = []
    for d in range(n_days):
        day = date(2026, 11, 1) + timedelta(days=d)
        y = d % 2
        qid = f"power-{day}"
        rows.append(scored("ml", 0.9 if y else 0.1, y, day, qid=qid))
        rows.append(scored("base_rate", 0.1 if y else 0.9, y, day, qid=qid))
    return rows


def test_weights_follow_loss_and_sum_to_one() -> None:
    m = bd.train(history(), ASOF)
    w = m.weights("power", ["ml", "base_rate"])
    assert w["ml"] > 0.99 and sum(w.values()) == pytest.approx(1.0)
    assert m.rounds["power"] > 0


def test_no_history_means_the_uniform_prior_and_it_is_recorded() -> None:
    m = bd.train([], ASOF)
    assert m.weights("power", ["ml", "base_rate"]) == {"ml": 0.5, "base_rate": 0.5}
    f = bd.BanditForecaster(m).forecast(
        question(), {"peer_forecasts": {"ml": 0.8, "base_rate": 0.4}}, ASOF
    )
    assert isinstance(f, Forecast) and f.probability == pytest.approx(0.6) and f.meta["rounds"] == 0


def test_recent_questions_are_not_used_leakage_lag() -> None:
    rows = history(20)
    late = ASOF.date() - timedelta(days=bd.LAG_DAYS - 1)  # inside the lag: outcome not yet known
    rows.append(scored("ml", 0.0, 1, late, qid="late"))
    base = bd.train(history(20), ASOF)
    with_late = bd.train(rows, ASOF)
    assert with_late.rounds == base.rounds and with_late.stats == base.stats


def test_the_blend_moves_towards_the_trusted_expert() -> None:
    m = bd.train(history(), ASOF)
    f = bd.BanditForecaster(m).forecast(
        question(), {"peer_forecasts": {"ml": 0.9, "base_rate": 0.1}}, ASOF
    )
    assert isinstance(f, Forecast) and f.probability > 0.85
    assert f.meta["experimental"] is True and set(f.meta["weights"]) == {"ml", "base_rate"}


def test_fewer_than_two_experts_is_a_skip_with_a_reason() -> None:
    out = bd.BanditForecaster(bd.train([], ASOF)).forecast(
        question(), {"peer_forecasts": {"ml": 0.7}}, ASOF
    )
    assert (
        isinstance(out, Skip) and out.reason_code == "model_missing" and "at least 2" in out.detail
    )


def test_version_names_the_algorithm_not_the_data() -> None:
    a = bd.BanditForecaster(bd.train(history(), ASOF)).version()
    b = bd.BanditForecaster(bd.train([], ASOF)).version()
    assert a == b and a.startswith("hedge-r1|brier|")


def test_hedge_eta_shrinks_with_rounds() -> None:
    assert bd.hedge_eta(10, 5) > bd.hedge_eta(1000, 5) > 0


def test_thompson_pick_is_seeded_and_prefers_the_better_expert() -> None:
    rows = history(40)
    picks = [bd.thompson_pick("power", rows, ASOF, f"q{i}", ("ml", "base_rate")) for i in range(30)]
    assert picks.count("ml") > 25
    assert bd.thompson_pick("power", rows, ASOF, "same", ("ml", "base_rate")) == bd.thompson_pick(
        "power", rows, ASOF, "same", ("ml", "base_rate")
    )


def test_wiring_registers_it_only_with_the_flag_and_after_its_peers(tmp_path) -> None:
    from factories import B

    from arena.config import Settings
    from arena.ledger import Ledger
    from arena.ops.wiring import build_forecasters

    off, _ = build_forecasters(Ledger(tmp_path), [], Settings.from_env({}), B, dry_run=True)
    assert "bandit_hedge" not in [f.forecaster_id for f in off]
    on, _ = build_forecasters(
        Ledger(tmp_path), [], Settings.from_env({"ARENA_BANDIT": "1"}), B, dry_run=True
    )
    ids = [f.forecaster_id for f in on]
    assert ids.index("bandit_hedge") > ids.index("agent") and ids.index("bandit_hedge") > ids.index(
        "ml"
    )
    (b,) = [f for f in on if f.forecaster_id == "bandit_hedge"]
    assert b.needs_peers is True
