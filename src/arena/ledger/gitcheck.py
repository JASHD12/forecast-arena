"""`arena ledger verify --git`: check from branch history that batches landed before lock.

This is evidence, not proof: git committer dates are set by whoever commits. What makes a
silent edit detectable is the combination of the public branch history (every clone keeps
it), the hash chain, and the GitHub Actions run logs. See docs/METHODS.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from arena.ledger import layout
from arena.ledger.gitsync import git
from arena.ledger.store import Ledger
from arena.models import Question


def commits_touching(repo: Path, paths: list[str]) -> list[tuple[str, datetime]]:
    """(sha, committer time) for every commit on HEAD that touched any of `paths`."""
    out = git(["log", "--format=%H %ct", "--", *paths], cwd=repo)
    rows = []
    for line in out.splitlines():
        sha, ts = line.split()
        rows.append((sha, datetime.fromtimestamp(int(ts), tz=UTC)))
    return rows


def verify_git(ledger: Ledger) -> list[str]:
    """Return problems found in the history of the ledger checkout (empty list = pass)."""
    repo = ledger.root
    errors: list[str] = []
    for rel in ledger.list_files("chain/batch"):
        batch = layout.batch_seal_date(rel)
        if batch is None:
            continue
        questions = [
            r for r in ledger.read(layout.questions_path(batch)) if isinstance(r, Question)
        ]
        if not questions:
            errors.append(f"batch {batch}: sealed but has no questions")
            continue
        lock = min(q.lock_time for q in questions)
        paths = [layout.questions_path(batch), layout.forecasts_path(batch),
                 layout.players_path(batch), rel]  # fmt: skip
        commits = commits_touching(repo, paths)
        if not any(rel in _changed(repo, sha) for sha, _ in commits):
            errors.append(f"batch {batch}: seal {rel} is not committed")
        for sha, when in commits:
            if when >= lock:
                errors.append(
                    f"batch {batch}: commit {sha[:10]} at {when.isoformat()} touched the batch "
                    f"at or after lock {lock.isoformat()}"
                )
    return errors


def _changed(repo: Path, sha: str) -> set[str]:
    out = git(["show", "--format=", "--name-only", sha], cwd=repo)
    return set(out.splitlines())
