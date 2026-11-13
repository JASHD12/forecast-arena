"""Paths inside the ledger directory (SPEC 6). All paths are POSIX, relative to the root."""

from __future__ import annotations

import re
from datetime import date

FAMILIES: dict[str, frozenset[str]] = {
    "questions": frozenset({"question"}),
    "forecasts": frozenset({"forecast", "skip"}),
    "resolutions": frozenset({"resolution", "void"}),
    #: T161: public players' forecasts, one file per batch, written before the lock and
    #: after the batch seal (which covers only the machine forecasts).
    "players": frozenset({"forecast"}),
}

GENESIS_CHAIN = "0" * 64

_DATED_JSONL = re.compile(
    r"^(questions|forecasts|resolutions|players|agent_traces)/(\d{4})/(\d{2})/(\d{2})\.jsonl$"
)
_RUN = re.compile(r"^runs/(\d{4})/(\d{2})/(\d{2})-[a-z0-9_]+-\d+\.json$")
_HEALTH = re.compile(r"^health/(\d{4})/(\d{2})/(\d{2})-[a-z0-9_]+-\d+\.json$")
_SNAPSHOT = re.compile(r"^snapshots/[a-z0-9_]+/(\d{4})/(\d{2})/(\d{2})/.+$")
_BATCH_SEAL = re.compile(r"^chain/batch/(\d{4})-(\d{2})-(\d{2})\.json$")
_DAY_SEAL = re.compile(r"^chain/day/(\d{4})-(\d{2})-(\d{2})\.json$")


def _ymd(d: date) -> str:
    return f"{d.year:04d}/{d.month:02d}/{d.day:02d}"


def questions_path(batch: date) -> str:
    """Questions of a batch."""
    return f"questions/{_ymd(batch)}.jsonl"


def forecasts_path(batch: date) -> str:
    """Forecasts and skips of a batch."""
    return f"forecasts/{_ymd(batch)}.jsonl"


def players_path(batch: date) -> str:
    """Public players' forecasts for a batch (T161)."""
    return f"players/{_ymd(batch)}.jsonl"


def resolutions_path(written_on: date) -> str:
    """Resolutions and voids, by the UTC date they were written."""
    return f"resolutions/{_ymd(written_on)}.jsonl"


def agent_traces_path(batch: date) -> str:
    """Compact agent tool-call logs of a batch."""
    return f"agent_traces/{_ymd(batch)}.jsonl"


def run_path(day: date, job: str, n: int) -> str:
    """The n-th run manifest of `job` started on UTC `day`."""
    return f"runs/{_ymd(day)}-{job}-{n}.json"


def snapshot_dir(domain: str, day: date) -> str:
    """Directory for compressed as-of inputs and evidence."""
    return f"snapshots/{domain}/{_ymd(day)}"


def batch_seal_path(batch: date) -> str:
    """Batch seal file."""
    return f"chain/batch/{batch.isoformat()}.json"


def day_seal_path(day: date) -> str:
    """Day seal file."""
    return f"chain/day/{day.isoformat()}.json"


def health_path(day: date, job: str, n: int) -> str:
    """Path of the n-th health report of a job on a day (sealed with that day)."""
    return f"health/{_ymd(day)}-{job}-{n}.json"


OFFICIAL_START_PATH = "meta/official_start.json"


def family_of(path: str) -> str | None:
    """`questions`, `forecasts` or `resolutions` for a record JSONL path, else None."""
    m = _DATED_JSONL.match(path)
    if m and m.group(1) in FAMILIES:
        return m.group(1)
    return None


def day_of(path: str) -> date | None:
    """The ledger day a file belongs to, for day sealing. Day seals themselves: None."""
    for pattern in (_DATED_JSONL, _RUN, _HEALTH, _SNAPSHOT, _BATCH_SEAL):
        m = pattern.match(path)
        if m:
            y, mo, d = (int(g) for g in m.groups()[-3:])
            return date(y, mo, d)
    return None


def day_seal_date(path: str) -> date | None:
    """The day a `chain/day/` seal file seals, else None."""
    m = _DAY_SEAL.match(path)
    return date(*(int(g) for g in m.groups())) if m else None


def batch_seal_date(path: str) -> date | None:
    """The batch a `chain/batch/` seal file seals, else None."""
    m = _BATCH_SEAL.match(path)
    return date(*(int(g) for g in m.groups())) if m else None
