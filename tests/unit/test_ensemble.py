"""T090: the ensemble stays inactive below its threshold and trains only on official data."""

import random
from datetime import UTC, date, datetime, timedelta

import pytest
from factories import question
from power_fixtures import fixture_domain

from arena.clock import FixedClock
from arena.forecasters.ensemble import (
    MEMBERS,
    EnsembleForecaster,
    common_rows,
    eligible_rows,
    is_active,
    train,
    training_cutoff,
)
from arena.models import Forecast, Question, Skip
from arena.scoring.core import Scored

START = date(2026, 10, 5)
ASOF = datetime(2026, 12, 14, 7, 30, tzinfo=UTC)  # a Monday: cutoff is 2 days before it


def _scored(days: int, start: date = START, members=MEMBERS, seed: int = 1) -> list[Scored]:
    rng = random.Random(seed)
    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        for k in range(3):
            y = rng.randint(0, 1)
            base = 0.5 + (0.3 if y else -0.3) * rng.random()  # informative but noisy
            for f in members:
                p = min(0.95, max(0.05, base + rng.uniform(-0.1, 0.1)))
                out.append(Scored(f"{d}-{k}", f, "1", "power" if k < 2 else "weather", d, p, y))
    return out


def test_inactive_without_an_official_start_or_below_the_threshold() -> None:
    sc = _scored(80)
    assert train(sc, None, ASOF) is None  # rehearsal only: never trains
    few = _scored(10)  # 30 questions x 5 members = 150 < 300
    assert not is_active(eligible_rows(few, START, ASOF))
    assert train(few, START, ASOF) is None


def test_activates_at_300_common_set_forecasts_and_predicts() -> None:
    sc = _scored(40)  # 120 questions x 5 members = 600
    rows = eligible_rows(sc, START, ASOF)
    assert is_active(rows) and len(rows) == 120
    model = train(sc, START, ASOF)
    assert model is not None and model.version.startswith("ensemble-lr-r1-2026-12-12-n")
    p_hi = model.probability({f: 0.9 for f in MEMBERS}, "power")
    p_lo = model.probability({f: 0.1 for f in MEMBERS}, "power")
    assert 0 < p_lo < 0.5 < p_hi < 1


def test_trains_only_on_official_rows_resolved_before_this_weeks_fit() -> None:
    rehearsal = _scored(20, start=START - timedelta(days=20), seed=2)
    official = _scored(40, seed=3)
    cutoff = training_cutoff(ASOF)
    late = _scored(5, start=cutoff + timedelta(days=1), seed=4)  # not yet resolved at the fit
    rows = eligible_rows(rehearsal + official + late, START, ASOF)
    assert rows and all(START <= r.batch_date <= cutoff for r in rows)
    assert all(r.question_id.split("-")[0] != "" for r in rows)


def test_a_question_needs_every_member() -> None:
    sc = _scored(2)
    partial = [s for s in sc if not (s.forecaster_id == "agent" and s.question_id.endswith("-0"))]
    assert len(common_rows(partial)) == len(common_rows(sc)) - 2


def _q(domain: str = "power") -> Question:
    return question().model_copy(update={"domain": domain})


def test_forecaster_combines_peers_and_skips_when_one_is_missing() -> None:
    model = train(_scored(40), START, ASOF)
    assert model is not None
    f = EnsembleForecaster(model)
    ok = f.forecast(_q(), {"peer_forecasts": {m: 0.7 for m in MEMBERS}}, ASOF)
    assert isinstance(ok, Forecast) and 0 < ok.probability < 1 and ok.forecaster_id == "ensemble"
    assert set(ok.meta["inputs"]) == set(MEMBERS)
    gap = f.forecast(_q(), {"peer_forecasts": {"base_rate": 0.5}}, ASOF)
    assert isinstance(gap, Skip) and gap.reason_code == "model_missing"
    unseen = f.forecast(_q("markets"), {"peer_forecasts": {m: 0.5 for m in MEMBERS}}, ASOF)
    assert isinstance(unseen, Skip) and "markets" in unseen.detail


def test_single_outcome_training_data_is_refused_not_guessed() -> None:
    sc = [Scored(s.question_id, s.forecaster_id, "1", s.domain, s.batch_date, s.probability, 1)
          for s in _scored(40)]  # fmt: skip
    assert train(sc, START, ASOF) is None


@pytest.mark.parametrize("p", [0.0, 1.0])
def test_extreme_inputs_are_clipped(p: float) -> None:
    model = train(_scored(40), START, ASOF)
    assert model is not None
    out = model.probability({f: p for f in MEMBERS}, "power")
    assert 0 < out < 1


def test_morning_job_gives_a_combining_forecaster_the_peers_forecasts(tmp_path) -> None:
    """The job passes the forecasts already written for the same question, and nothing else."""
    from test_jobs import B, setup

    from arena.ledger import layout
    from arena.models import Forecast as F
    from arena.ops.jobs import morning

    seen: dict[str, dict[str, float]] = {}

    class Combiner:
        forecaster_id = "combiner"
        needs_peers = True

        def version(self) -> str:
            return "1"

        def forecast(self, q, ctx, asof):
            seen[q.question_id] = dict(ctx.get("peer_forecasts", {}))
            return F(
                forecast_id=f"{q.question_id}::combiner", question_id=q.question_id,
                forecaster_id="combiner", forecaster_version="1", probability=0.5, created_at=asof,
            )  # fmt: skip

    led, clock, doms, fcs = setup(tmp_path, datetime(2026, 11, 2, 5, 30, tzinfo=UTC))
    morning(led, B, clock, doms, [*fcs, Combiner()])
    qs = [r for r in led.read(layout.questions_path(B)) if isinstance(r, Question)]
    assert qs and set(seen) == {q.question_id for q in qs}
    for peers in seen.values():
        assert set(peers) == {"base_rate", "persistence"}  # the broken forecaster wrote a skip


def _ledger_with_official_rows(tmp_path, official_start: date | None, days: int = 14):
    """A real ledger folder: `days` batch days x 6 power questions, all four members answered
    and every question resolved; `meta/official_start.json` is written when a date is given."""
    import json

    from factories import forecast, resolution

    from arena.ledger import Ledger, layout

    led = Ledger(tmp_path / "ledger")
    templates = ["mean_gt", "max_gt", "min_lt", "spread_gt", "evening_gt", "up_vs_today"]
    rng = random.Random(7)
    for i in range(days):
        d = date(2026, 11, 23) + timedelta(days=i)
        qs = [question(batch=d, template=t) for t in templates]
        fs, rs = [], []
        for q in qs:
            y = rng.randint(0, 1)
            rs.append(resolution(q, y))
            for m in MEMBERS:
                fs.append(
                    forecast(q, m, min(0.95, max(0.05, 0.5 + (0.3 if y else -0.3) * rng.random())))
                )
        led.append(layout.questions_path(d), qs)
        led.append(layout.forecasts_path(d), fs)
        led.append(layout.resolutions_path(d), rs)
    if official_start is not None:
        led.write_raw(
            layout.OFFICIAL_START_PATH,
            json.dumps({"official_start": official_start.isoformat()}).encode(),
        )
    return led


def test_live_ensemble_is_registered_last_only_with_an_official_start(tmp_path) -> None:
    """T093: the switch is the official start; no code or flag change is needed after it."""
    from arena.ops.wiring import build_forecasters, live_ensemble

    asof = datetime(2026, 12, 7, 7, 30, tzinfo=UTC)  # Monday after 12 official days
    none = _ledger_with_official_rows(tmp_path / "a", None)
    assert live_ensemble(none, asof) is None  # rehearsal only: inactive

    led = _ledger_with_official_rows(tmp_path / "b", date(2026, 11, 23))
    ens = live_ensemble(led, asof)
    assert ens is not None and ens.forecaster_id == "ensemble"
    assert ens.version().startswith("ensemble-lr-r1-2026-12-05-n")  # cutoff: Monday minus 2 days

    early = datetime(2026, 11, 30, 7, 30, tzinfo=UTC)  # first Monday: 6 days x 6 = 36 questions
    assert (
        live_ensemble(led, early) is None
    )  # under 75 questions (300 rows of 4 members): still inactive

    from arena.config import Settings

    settings = Settings(llm_local=False, agent_graph=False)
    kw = {"dry_run": True, "clock": FixedClock(asof)}
    forecasters, _ = build_forecasters(led, [fixture_domain()], settings, **kw)
    assert [f.forecaster_id for f in forecasters][-1] == "ensemble"
    forecasters, _ = build_forecasters(none, [fixture_domain()], settings, **kw)
    assert "ensemble" not in [f.forecaster_id for f in forecasters]
