from datetime import date

import pytest
from factories import question
from power_fixtures import fixture_domain

from arena.backtest.harness import (
    BacktestError,
    BacktestRecord,
    BacktestStore,
    walk_forward,
)
from arena.forecasters.baselines import BaseRate, Persistence
from arena.ledger import Ledger, LedgerError, layout


def run():
    return walk_forward(
        "bt-test",
        fixture_domain(),
        lambda h: [BaseRate(h), Persistence(h)],
        date(2026, 9, 1),
        date(2026, 10, 20),
        warmup=20,
    )


def test_walk_forward_records_are_labelled_and_leak_free() -> None:
    res = run()
    assert res.records and all(r.label == "backtest" for r in res.records)
    assert {r.forecaster_id for r in res.records} == {"base_rate", "persistence"}
    assert min(r.batch_date for r in res.records) == date(2026, 9, 21)
    used = [r.meta["instances"] for r in res.records if r.forecaster_id == "base_rate"]
    assert max(used) <= 50  # history only grows with batches whose outcome was known
    assert all(r.outcome in (0, 1) for r in res.records)


def test_backtest_records_cannot_enter_the_live_ledger(tmp_path) -> None:
    led = Ledger(tmp_path / "ledger")
    q = question()
    led.append(layout.questions_path(q.batch_date), [q])
    rec = BacktestRecord(
        run_id="x",
        question_id=q.question_id,
        domain="power",
        template="mean_gt",
        entity="DE_LU",
        batch_date=q.batch_date,
        forecaster_id="ml",
        forecaster_version="1",
        probability=0.5,
        outcome=1,
    )
    with pytest.raises(LedgerError):
        led.append(layout.forecasts_path(q.batch_date), [rec])  # type: ignore[list-item]
    with pytest.raises(BacktestError):
        BacktestStore(tmp_path / "ledger" / "backtests")


def test_store_round_trip_and_no_overwrite(tmp_path) -> None:
    res = run()
    store = BacktestStore(tmp_path / "backtests")
    path = store.write(res.run_id, res.records, {"domain": "power"})
    assert '"label": "backtest"' in (path / "meta.json").read_text()
    assert store.read(res.run_id) == res.records
    with pytest.raises(BacktestError):
        store.write(res.run_id, res.records, {})
