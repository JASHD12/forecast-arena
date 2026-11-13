"""T161: public players' intake (late, duplicate and invalid rows; append-only; lock)."""

from datetime import UTC, date, datetime

import pytest
from power_fixtures import fixture_domain

from arena.clock import FixedClock
from arena.forecasters.players import (
    PREFIX,
    is_player,
    parse_players_csv,
    player_id,
    select,
)
from arena.ledger import Ledger, layout
from arena.ledger.verify import verify
from arena.models import Forecast, Question
from arena.ops.jobs import evening, players

B = date(2026, 11, 2)
HEADER = "code,question_id,probability,submitted_at,consent\n"
ALICE, BOB = "alice-code-0001", "bob-code-000002"


def ledger_with_questions(tmp_path) -> tuple[Ledger, list[Question]]:
    led = Ledger(tmp_path / "ledger")
    evening(led, B, FixedClock(datetime(2026, 11, 1, 18, tzinfo=UTC)), [fixture_domain()])
    qs = [q for q in led.read(layout.questions_path(B)) if isinstance(q, Question)]
    assert qs
    return led, qs


def csv_of(*rows: tuple[str, str, str, str, str]) -> str:
    return HEADER + "".join(",".join(r) + "\n" for r in rows)


def test_player_ids_are_pseudonyms() -> None:
    pid = player_id(ALICE)
    assert pid.startswith(PREFIX) and len(pid) == len(PREFIX) + 8 and ALICE not in pid
    assert is_player(pid) and not is_player("base_rate")


def test_invalid_rows_are_counted_not_guessed() -> None:
    text = csv_of(
        ("short", "q", "0.5", "2026-11-02T08:00:00+00:00", "yes"),  # bad code
        (ALICE, "q", "0.5", "2026-11-02T08:00:00+00:00", "no"),  # no consent
        (ALICE, "q", "abc", "2026-11-02T08:00:00+00:00", "yes"),  # bad value
        (ALICE, "q", "0.5", "yesterday", "yes"),  # bad time
        (ALICE, "", "0.5", "2026-11-02T08:00:00+00:00", "yes"),  # no question
        (ALICE, "q", "1.5", "2026-11-02T08:00:00+00:00", "yes"),  # out of range
        (ALICE, "q", "nan", "2026-11-02T08:00:00+00:00", "yes"),  # NaN
        (ALICE, "q", "0.3", "2026-11-02T08:00:00+00:00", "Yes"),  # valid
    )
    intake = parse_players_csv(text)
    assert len(intake.rows) == 1 and intake.rows[0].player == player_id(ALICE)
    assert intake.rejected == {"bad_code": 1, "no_consent": 1, "bad_value": 3,
                               "bad_probability": 2}  # fmt: skip
    with pytest.raises(ValueError, match="header"):
        parse_players_csv("token,question_id,probability,submitted_at\n")


def test_late_duplicate_and_other_rows(tmp_path) -> None:
    _, qs = ledger_with_questions(tmp_path)
    q, asof = qs[0], datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
    intake = parse_players_csv(csv_of(
        (ALICE, q.question_id, "0.2", "2026-11-01T19:00:00+00:00", "yes"),
        (ALICE, q.question_id, "0.7", "2026-11-02T08:00:00+00:00", "yes"),  # latest wins
        (ALICE, q.question_id, "0.4", "2026-11-01T20:00:00+00:00", "yes"),  # older
        (BOB, q.question_id, "0.9", "2026-11-02T09:30:00+00:00", "yes"),  # at the lock
        (BOB, q.question_id, "0.8", "2026-11-02T09:05:00+00:00", "yes"),  # after intake
        (BOB, "power-unknown-v2", "0.5", "2026-11-02T08:00:00+00:00", "yes"),
    ))  # fmt: skip
    winners, dropped = select(intake, qs, asof)
    assert {k: v.probability for k, v in winners.items()} == {
        (q.question_id, player_id(ALICE)): 0.7
    }
    assert dropped == {"superseded": 2, "late": 1, "after_intake": 1, "other_question": 1}


def test_intake_writes_before_lock_and_never_replaces(tmp_path) -> None:
    led, qs = ledger_with_questions(tmp_path)
    q1, q2 = qs[0], qs[1]
    first = parse_players_csv(csv_of(
        (ALICE, q1.question_id, "0.7", "2026-11-02T08:00:00+00:00", "yes"),
    ))  # fmt: skip
    clock = FixedClock(datetime(2026, 11, 2, 9, 0, tzinfo=UTC))
    r = players(led, B, clock, first)
    assert r.written == {"player_forecasts": 1}
    path = layout.players_path(B)
    recs = [x for x in led.read(path) if isinstance(x, Forecast)]
    assert [(f.forecaster_id, f.probability) for f in recs] == [(player_id(ALICE), 0.7)]
    assert recs[0].created_at == clock.now() < q1.lock_time
    assert recs[0].meta["submitted_at"] == "2026-11-02T08:00:00+00:00"
    # second run: Alice changed her mind (not replaced), Bob and a new question are added
    second = parse_players_csv(csv_of(
        (ALICE, q1.question_id, "0.1", "2026-11-02T09:10:00+00:00", "yes"),
        (ALICE, q2.question_id, "0.6", "2026-11-02T09:10:00+00:00", "yes"),
        (BOB, q1.question_id, "0.4", "2026-11-02T09:12:00+00:00", "yes"),
    ))  # fmt: skip
    clock.set(datetime(2026, 11, 2, 9, 15, tzinfo=UTC))
    assert players(led, B, clock, second).written == {"player_forecasts": 2}
    got = {(f.question_id, f.forecaster_id): f.probability
           for f in led.read(path) if isinstance(f, Forecast)}  # fmt: skip
    assert got[(q1.question_id, player_id(ALICE))] == 0.7  # the first record stands
    assert got[(q2.question_id, player_id(ALICE))] == 0.6
    assert got[(q1.question_id, player_id(BOB))] == 0.4
    assert players(led, B, clock, second).written == {}  # idempotent
    assert verify(led).ok
    from arena.scoring.core import load

    assert not any(is_player(f.forecaster_id) for f in load(led).forecasts)  # kept apart


def test_intake_refuses_late_wrong_day_and_unconfigured(tmp_path) -> None:
    led, qs = ledger_with_questions(tmp_path)
    intake = parse_players_csv(csv_of(
        (ALICE, qs[0].question_id, "0.7", "2026-11-02T08:00:00+00:00", "yes"),
    ))  # fmt: skip
    at_lock = FixedClock(datetime(2026, 11, 2, 9, 30, tzinfo=UTC))
    r = players(led, B, at_lock, intake)
    assert r.late and r.written == {}
    assert "not today's" in players(led, B, FixedClock(datetime(2026, 11, 1, 20, tzinfo=UTC)),
                                    intake).warnings[0]  # fmt: skip
    ok = FixedClock(datetime(2026, 11, 2, 9, 0, tzinfo=UTC))
    assert "no players CSV" in players(led, B, ok, None).warnings[0]
    assert players(led, B, ok, intake, dry_run=True).written == {"player_forecasts": 1}
    assert not led.exists(layout.players_path(B))


def test_verify_catches_a_backdated_player_forecast(tmp_path) -> None:
    led, qs = ledger_with_questions(tmp_path)
    bad = Forecast(forecast_id=f"{qs[0].question_id}::{player_id(ALICE)}",
                   question_id=qs[0].question_id, forecaster_id=player_id(ALICE),
                   forecaster_version="player-r1", probability=0.5,
                   created_at=datetime(2026, 11, 2, 10, tzinfo=UTC))  # fmt: skip
    led.append(layout.players_path(B), [bad])
    rep = verify(led)
    assert not rep.ok and "is not before lock" in rep.summary()
