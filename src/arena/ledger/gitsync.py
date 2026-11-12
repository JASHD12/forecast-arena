"""Keep `./_ledger` in sync with the `ledger` branch: clone or create, commit, push.

Rules (SPEC 6): commit message `ledger: <job> <date>`; on a rejected push, `pull --rebase`
and retry, up to five attempts; never force-push; never rewrite history.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

LEDGER_BRANCH = "ledger"
MAX_PUSH_ATTEMPTS = 5


class GitError(Exception):
    """A git command failed."""


@dataclass(frozen=True)
class GitIdentity:
    """Author/committer identity used for ledger commits."""

    name: str = "forecast-arena-bot"
    email: str = "forecast-arena-bot@users.noreply.github.com"


def git(args: Sequence[str], cwd: Path, identity: GitIdentity | None = None) -> str:
    """Run one git command and return stdout; raise GitError with stderr on failure."""
    ident = identity or GitIdentity()
    cmd = [
        "git",
        "-c", f"user.name={ident.name}",
        "-c", f"user.email={ident.email}",
        "-c", "commit.gpgsign=false",
        *args,
    ]  # fmt: skip
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {res.stderr.strip() or res.stdout.strip()}")
    return res.stdout.strip()


def remote_has_branch(remote: str, branch: str, cwd: Path) -> bool:
    """True if `remote` (URL or path) has `branch`."""
    out = git(["ls-remote", "--heads", remote, branch], cwd=cwd)
    return bool(out)


def ensure_checkout(remote: str, dest: Path, branch: str = LEDGER_BRANCH) -> str:
    """Make `dest` a checkout of `branch` from `remote`. Returns what was done.

    - existing checkout: `pull --rebase` if the remote branch exists ("updated");
    - remote has the branch: clone just that branch ("cloned");
    - otherwise: initialise a new repository whose first branch is `branch`, which is
      an orphan by construction, with `origin` pointing at `remote` ("created").
    """
    dest = Path(dest)
    if (dest / ".git").exists():
        if remote_has_branch("origin", branch, dest):
            git(["pull", "--rebase", "origin", branch], cwd=dest)
            return "updated"
        return "unchanged"
    if dest.exists() and any(dest.iterdir()):
        raise GitError(f"{dest} exists, is not empty and is not a git checkout")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if remote_has_branch(remote, branch, dest.parent):
        git(["clone", "--quiet", "--branch", branch, "--single-branch", remote, str(dest)],
            cwd=dest.parent)  # fmt: skip
        return "cloned"
    dest.mkdir(exist_ok=True)
    git(["init", "--quiet", "-b", branch], cwd=dest)
    git(["remote", "add", "origin", remote], cwd=dest)
    return "created"


def commit_and_push(
    dest: Path,
    job: str,
    day: date,
    *,
    branch: str = LEDGER_BRANCH,
    identity: GitIdentity | None = None,
    max_attempts: int = MAX_PUSH_ATTEMPTS,
) -> str | None:
    """Commit everything in `dest` as `ledger: <job> <date>` and push without force.

    Returns the pushed commit SHA, or None if there was nothing to commit and nothing
    unpushed. Raises GitError after `max_attempts` rejected pushes or a rebase conflict.
    """
    git(["add", "-A"], cwd=dest, identity=identity)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=dest, check=False)
    if staged.returncode != 0:
        git(["commit", "--quiet", "-m", f"ledger: {job} {day.isoformat()}"], cwd=dest,
            identity=identity)  # fmt: skip
    elif not _has_unpushed(dest, branch):
        return None
    last = ""
    for attempt in range(1, max_attempts + 1):
        try:
            git(["push", "--quiet", "origin", f"HEAD:refs/heads/{branch}"], cwd=dest)
            return git(["rev-parse", "HEAD"], cwd=dest)
        except GitError as exc:
            last = str(exc)
            if attempt == max_attempts:
                break
        try:
            git(["pull", "--rebase", "--quiet", "origin", branch], cwd=dest, identity=identity)
        except GitError as exc:
            subprocess.run(["git", "rebase", "--abort"], cwd=dest, capture_output=True,
                           check=False)  # fmt: skip
            raise GitError(f"rebase onto origin/{branch} failed; not forcing: {exc}") from exc
    raise GitError(f"push rejected {max_attempts} times; giving up without forcing: {last}")


def _has_unpushed(dest: Path, branch: str) -> bool:
    try:
        git(["rev-parse", "HEAD"], cwd=dest)
    except GitError:
        return False  # no commits at all
    try:
        out = git(["rev-list", "--count", f"origin/{branch}..HEAD"], cwd=dest)
    except GitError:
        return True  # remote branch unknown locally: everything is unpushed
    return int(out or "0") > 0
