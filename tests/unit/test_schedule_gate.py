"""T180: the gate that lets late, frequent scheduled runs do the work exactly once."""

from datetime import UTC, date, datetime

import pytest
from click.testing import CliRunner
from power_fixtures import fixture_domain

from arena.cli import main
from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.ops.jobs import evening, morning
from arena.ops.schedule import is_due

B = date(2026, 11, 2)


def at(day: int, h: int, m: int = 0) -> datetime:
    return datetime(2026, 11, day, h, m, tzinfo=UTC)


def test_morning_due_until_sealed_or_locked(tmp_path) -> None:
    led = Ledger(tmp_path / "l")
    for h in (0, 5, 9):
        assert is_due("morning", at(2, h), led).due
    assert not is_due("morning", at(2, 9, 30), led).due  # at the lock
    assert "lock" in is_due("morning", at(2, 13, 18), led).reason  # 2026-11-13 delay
    morning(led, B, FixedClock(at(2, 5, 30)), [fixture_domain()], [])
    assert led.exists(layout.batch_seal_path(B))
    d = is_due("morning", at(2, 7), led)
    assert not d.due and "sealed" in d.reason


def test_evening_due_once_after_the_window_opens(tmp_path) -> None:
    led = Ledger(tmp_path / "l")
    assert not is_due("evening", at(1, 15, 59), led).due
    assert is_due("evening", at(1, 16), led).due
    assert is_due("evening", at(1, 23, 50), led).due
    evening(led, B, FixedClock(at(1, 18)), [fixture_domain()])
    d = is_due("evening", at(1, 20), led)
    assert not d.due and "already published" in d.reason


def test_players_only_in_the_window_before_the_lock(tmp_path) -> None:
    led = Ledger(tmp_path / "l")
    assert not is_due("players", at(2, 8, 29), led).due
    assert is_due("players", at(2, 8, 30), led).due
    assert is_due("players", at(2, 9, 25), led).due
    assert not is_due("players", at(2, 9, 30), led).due
    with pytest.raises(ValueError):
        is_due("weekly", at(2, 8), led)


def test_cli_writes_the_github_output(tmp_path, monkeypatch) -> None:
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setattr("arena.cli.SystemClock", lambda: FixedClock(at(2, 6)))
    r = CliRunner().invoke(
        main,
        [
            "--ledger-dir",
            str(tmp_path / "l"),
            "--date",
            "2026-11-02",
            "schedule",
            "due",
            "--job",
            "morning",
        ],
    )
    assert r.exit_code == 0, r.output
    assert out.read_text().strip() == "due=true"
    assert r.output.startswith("morning: due (")
