from datetime import UTC, datetime
from pathlib import Path

from factories import B, forecast, question

from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.ledger.gitcheck import verify_git
from arena.ledger.gitsync import git
from arena.ledger.seal import seal_batch


def commit(repo: Path, msg: str, when: str) -> None:
    git(["add", "-A"], cwd=repo)
    env = {"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when}
    git(["commit", "--quiet", "-m", msg], cwd=repo, env=env)


def build(tmp_path: Path, when: str) -> Ledger:
    git(["init", "--quiet", "-b", "ledger"], cwd=tmp_path)
    led = Ledger(tmp_path)
    q = question("A", B)
    led.append(layout.questions_path(B), [q])
    led.append(layout.forecasts_path(B), [forecast(q)])
    seal_batch(led, B, FixedClock(datetime(2026, 11, 12, 6, tzinfo=UTC)))
    commit(tmp_path, "ledger: morning 2026-11-12", when)
    return led


def test_batch_committed_before_lock_passes(tmp_path: Path) -> None:
    assert verify_git(build(tmp_path, "2026-11-12T06:05:00Z")) == []


def test_fabricated_late_commit_fails(tmp_path: Path) -> None:
    errors = verify_git(build(tmp_path, "2026-11-12T09:31:00Z"))
    assert errors and "after lock" in errors[0]


def test_later_commit_touching_sealed_batch_fails(tmp_path: Path) -> None:
    led = build(tmp_path, "2026-11-12T06:05:00Z")
    p = led.abspath(layout.forecasts_path(B))
    p.write_text(p.read_text())  # no change in content
    p.write_text(p.read_text().replace("0.6", "0.9"))
    commit(tmp_path, "sneaky edit", "2026-11-13T10:00:00Z")
    assert any("after lock" in e for e in verify_git(led))


def test_uncommitted_seal_fails(tmp_path: Path) -> None:
    git(["init", "--quiet", "-b", "ledger"], cwd=tmp_path)
    led = Ledger(tmp_path)
    q = question("A", B)
    led.append(layout.questions_path(B), [q])
    commit(tmp_path, "questions only", "2026-11-12T06:00:00Z")
    seal_batch(led, B, FixedClock(datetime(2026, 11, 12, 6, tzinfo=UTC)))
    assert any("not committed" in e for e in verify_git(led))
