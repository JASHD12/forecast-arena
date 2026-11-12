"""Run manifests (SPEC 5, 6): one JSON file per job run under `runs/`, success or failure."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from importlib import metadata
from pathlib import Path

from arena.clock import Clock
from arena.ledger import layout
from arena.ledger.store import Ledger
from arena.models import RunManifest

TRACKED_PACKAGES = ("forecast-arena", "pydantic", "click")
MAX_ERROR_CHARS = 500


@dataclass
class RunRecorder:
    """Mutable collector a job writes to while it runs."""

    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    llm_usage: dict[str, int] = field(default_factory=dict)
    source_availability: dict[str, datetime] = field(default_factory=dict)

    def count(self, key: str, n: int = 1) -> None:
        """Add `n` to a counter."""
        self.counts[key] = self.counts.get(key, 0) + n

    def warn(self, message: str) -> None:
        """Record a warning (also shown on the Status page)."""
        self.warnings.append(message)

    def add_llm_usage(self, **usage: int) -> None:
        """Add token/request counts as reported by the API's own usage fields."""
        for key, value in usage.items():
            self.llm_usage[key] = self.llm_usage.get(key, 0) + int(value)


def code_sha(repo_dir: Path | None = None) -> str:
    """Commit SHA of the running code: `GITHUB_SHA` in Actions, else `git rev-parse`."""
    env_sha = os.environ.get("GITHUB_SHA")
    if env_sha:
        return env_sha
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir or Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    return res.stdout.strip() if res.returncode == 0 else "unknown"


def package_versions() -> dict[str, str]:
    """Installed versions of the packages that shape results."""
    out = {}
    for name in TRACKED_PACKAGES:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = "not-installed"
    return out


def next_run_number(ledger: Ledger, day: date, job: str) -> int:
    """1 + the highest existing run number for (day, job)."""
    n = 1
    while ledger.exists(layout.run_path(day, job, n)):
        n += 1
    return n


@contextmanager
def run_manifest(
    ledger: Ledger, job: str, batch_date: date, clock: Clock, *, dry_run: bool = False
) -> Iterator[RunRecorder]:
    """Record a job run. The manifest is written on success and on failure (then re-raised).

    The file is named by the UTC date the run *started*, so the day seal that covers it is
    always written by a later run.
    """
    started = clock.now()
    rec = RunRecorder()
    status, error = "ok", None
    try:
        yield rec
    except BaseException as exc:
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"[:MAX_ERROR_CHARS]
        raise
    finally:
        day = started.date()
        n = next_run_number(ledger, day, job)
        manifest = RunManifest(
            run_id=f"{day.isoformat()}-{job}-{n}",
            job=job,
            batch_date=batch_date,
            status=status,
            code_sha=code_sha(),
            package_versions=package_versions(),
            started_at=started,
            ended_at=clock.now(),
            dry_run=dry_run,
            counts=dict(rec.counts),
            warnings=list(rec.warnings),
            llm_usage=dict(rec.llm_usage),
            source_availability=dict(rec.source_availability),
            error=error,
        )
        ledger.write_json(layout.run_path(day, job, n), manifest)


def manifests_for_day(ledger: Ledger, day: date) -> list[RunManifest]:
    """All run manifests started on UTC `day` (used to sum LLM usage across runs)."""
    prefix = f"runs/{day.year:04d}/{day.month:02d}"
    out = []
    for rel in ledger.list_files(prefix):
        if layout.day_of(rel) == day:
            rec = ledger.read_json(rel)
            if isinstance(rec, RunManifest):
                out.append(rec)
    return out
