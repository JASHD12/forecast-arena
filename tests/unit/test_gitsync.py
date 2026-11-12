import subprocess
from datetime import date
from pathlib import Path

import pytest

from arena.ledger.gitsync import GitError, commit_and_push, ensure_checkout, git

D = date(2026, 11, 12)


@pytest.fixture
def remote(tmp_path: Path) -> str:
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--quiet", "--bare", str(bare)], check=True)
    return str(bare)


def log(remote: str, tmp: Path) -> list[str]:
    return git(["log", "--format=%s", "ledger"], cwd=Path(remote)).splitlines()


def test_first_run_creates_orphan_branch(remote: str, tmp_path: Path) -> None:
    dest = tmp_path / "_ledger"
    assert ensure_checkout(remote, dest) == "created"
    (dest / "questions").mkdir()
    (dest / "questions" / "a.jsonl").write_text("{}\n")
    sha = commit_and_push(dest, "morning", D)
    assert sha
    assert log(remote, tmp_path) == ["ledger: morning 2026-11-12"]
    parents = git(["rev-list", "--parents", "-n1", "ledger"], cwd=Path(remote)).split()
    assert len(parents) == 1, "first ledger commit has no parent (orphan)"


def test_normal_run_clones_and_appends(remote: str, tmp_path: Path) -> None:
    a = tmp_path / "a"
    ensure_checkout(remote, a)
    (a / "x").write_text("1\n")
    commit_and_push(a, "morning", D)
    b = tmp_path / "b"
    assert ensure_checkout(remote, b) == "cloned"
    assert (b / "x").read_text() == "1\n"
    (b / "y").write_text("2\n")
    commit_and_push(b, "resolve", D)
    assert commit_and_push(b, "resolve", D) is None, "nothing to do the second time"
    assert ensure_checkout(remote, a) == "updated"
    assert (a / "y").exists()
    assert log(remote, tmp_path) == ["ledger: resolve 2026-11-12", "ledger: morning 2026-11-12"]


def test_concurrent_push_rebases_and_keeps_both(remote: str, tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    ensure_checkout(remote, a)
    (a / "base").write_text("0\n")
    commit_and_push(a, "morning", D)
    ensure_checkout(remote, b)
    (a / "from_a").write_text("a\n")
    commit_and_push(a, "resolve", D)
    (b / "from_b").write_text("b\n")  # b has not seen a's second commit
    commit_and_push(b, "morning", D)
    msgs = log(remote, tmp_path)
    assert len(msgs) == 3
    tree = git(["ls-tree", "--name-only", "ledger"], cwd=Path(remote)).split()
    assert {"base", "from_a", "from_b"} <= set(tree)


def test_conflict_is_not_forced(remote: str, tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    ensure_checkout(remote, a)
    (a / "f").write_text("0\n")
    commit_and_push(a, "morning", D)
    ensure_checkout(remote, b)
    (a / "f").write_text("a\n")
    commit_and_push(a, "resolve", D)
    (b / "f").write_text("b\n")
    with pytest.raises(GitError, match="not forcing"):
        commit_and_push(b, "morning", D)
    assert git(["show", "ledger:f"], cwd=Path(remote)) == "a"


def test_refuses_non_empty_non_checkout(remote: str, tmp_path: Path) -> None:
    d = tmp_path / "busy"
    d.mkdir()
    (d / "file").write_text("x")
    with pytest.raises(GitError, match="not empty"):
        ensure_checkout(remote, d)
