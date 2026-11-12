from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from factories import B, question, resolution

from arena.forecasters.base import Instance, LedgerHistory, StaticHistory
from arena.forecasters.baselines import BaseRate, Persistence, laplace
from arena.ledger import Ledger, layout
from arena.models import Void

ASOF = datetime(2026, 11, 12, 6, tzinfo=UTC)
KEY = ("power", "mean_gt", "DE_LU")
TARGET = B + timedelta(days=1)


def hist(outcomes: list[int]) -> StaticHistory:
    n = len(outcomes)
    return StaticHistory(
        {KEY: [Instance(TARGET - timedelta(days=n - i), o) for i, o in enumerate(outcomes)]}
    )


def test_laplace() -> None:
    assert laplace(0, 0) == 0.5 and laplace(3, 4) == pytest.approx(4 / 6)


def test_base_rate_under_ten_is_half() -> None:
    f = BaseRate(hist([1] * 9)).forecast(question(), {}, ASOF)
    assert f.probability == 0.5 and f.meta["rule"] == "fewer_than_10"


def test_base_rate_smoothed_and_windowed() -> None:
    f = BaseRate(hist([1] * 10)).forecast(question(), {}, ASOF)
    assert f.probability == pytest.approx(11 / 12)
    f = BaseRate(hist([0] * 50 + [1] * 90)).forecast(question(), {}, ASOF)
    assert f.probability == pytest.approx(91 / 92) and f.meta["instances"] == 90
    assert f.created_at == ASOF and f.forecast_id.endswith("::base_rate")


def test_persistence_conditions_on_yesterday() -> None:
    # alternating 0,1,0,1,... ending in 1: after a 1 comes a 0 every time
    outcomes = [i % 2 for i in range(40)]
    f = Persistence(hist(outcomes)).forecast(question(), {}, ASOF)
    assert f.meta["yesterday"] == 1
    assert f.probability == pytest.approx(laplace(0, 19))


def test_persistence_falls_back_when_yesterday_unknown() -> None:
    h = StaticHistory({KEY: [Instance(TARGET - timedelta(days=d), 1) for d in range(3, 30)]})
    f = Persistence(h).forecast(question(), {}, ASOF)
    assert f.meta["fallback"] == "yesterday_unknown"
    assert f.probability == BaseRate(h).forecast(question(), {}, ASOF).probability


def test_persistence_falls_back_with_few_transitions() -> None:
    f = Persistence(hist([1] * 5)).forecast(question(), {}, ASOF)
    assert f.meta["fallback"] == "fewer_than_10_transitions" and f.probability == 0.5


def test_ledger_history_respects_asof_and_voids(tmp_path: Path) -> None:
    led = Ledger(tmp_path)
    for k in range(1, 4):
        b = B - timedelta(days=k)
        q = question("DE_LU", b)
        led.append(layout.questions_path(b), [q])
        led.append(layout.resolutions_path(b + timedelta(days=1)), [resolution(q, k % 2)])
    q_void = question("DE_LU", B - timedelta(days=4))
    led.append(layout.questions_path(q_void.batch_date), [q_void])
    led.append(
        layout.resolutions_path(B),
        [
            resolution(q_void),
            Void(question_id=q_void.question_id, reason_code="bug", voided_at=ASOF),
        ],
    )
    h = LedgerHistory(led)
    got = h.instances(*KEY, before=TARGET, asof=ASOF)
    assert [i.target_date for i in got] == [date(2026, 11, 10), date(2026, 11, 11), B]
    early = h.instances(*KEY, before=TARGET, asof=datetime(2026, 11, 10, 0, tzinfo=UTC))
    assert len(early) < len(got), "resolutions written after asof are invisible"
