"""Batch seals, day seals and the hash chain (SPEC 6).

Chain rule (also stated on the Methods page):

    lines        = sorted("path:sha256" for every file of day X)
    chain_sha256 = sha256( prev_chain_sha256 + "\\n" + "\\n".join(lines) + "\\n" )

`prev_chain_sha256` is the chain hash of the latest earlier day seal, or 64 zeros for the
first seal (genesis).
"""

from __future__ import annotations

import hashlib
from datetime import date

from arena.clock import Clock
from arena.ledger import layout
from arena.ledger.store import Ledger, LedgerError
from arena.models import BatchSeal, DaySeal


def sha256_bytes(data: bytes) -> str:
    """Hex SHA-256 of bytes."""
    return hashlib.sha256(data).hexdigest()


def file_sha256(ledger: Ledger, rel: str) -> str:
    """Hex SHA-256 of a ledger file's bytes."""
    return sha256_bytes(ledger.read_bytes(rel))


def chain_hash(prev_chain_sha256: str, files: dict[str, str]) -> str:
    """Chain hash for a day, from the previous chain hash and that day's file hashes."""
    lines = sorted(f"{path}:{sha}" for path, sha in files.items())
    payload = prev_chain_sha256 + "\n" + "\n".join(lines) + "\n"
    return sha256_bytes(payload.encode("utf-8"))


def batch_files(ledger: Ledger, batch: date) -> dict[str, str]:
    """Hashes of the questions and forecasts files of a batch (those that exist)."""
    paths = [layout.questions_path(batch), layout.forecasts_path(batch)]
    return {p: file_sha256(ledger, p) for p in paths if ledger.exists(p)}


def seal_batch(ledger: Ledger, batch: date, clock: Clock) -> BatchSeal:
    """Write `chain/batch/B.json`. After this the batch's two files are immutable."""
    rel = layout.batch_seal_path(batch)
    if ledger.exists(rel):
        existing = ledger.read_json(rel)
        assert isinstance(existing, BatchSeal)
        return existing
    files = batch_files(ledger, batch)
    if layout.questions_path(batch) not in files:
        raise LedgerError(f"no questions file for batch {batch}; nothing to seal")
    seal = BatchSeal(batch_date=batch, sealed_at=clock.now(), files=files)
    ledger.write_json(rel, seal)
    return seal


def day_files(ledger: Ledger, day: date) -> dict[str, str]:
    """Hashes of every ledger file that belongs to `day` (day seals excluded)."""
    return {
        rel: file_sha256(ledger, rel) for rel in ledger.list_files() if layout.day_of(rel) == day
    }


def day_seals(ledger: Ledger) -> list[DaySeal]:
    """All day seals in date order."""
    out = []
    for rel in ledger.list_files("chain/day"):
        if layout.day_seal_date(rel) is not None:
            rec = ledger.read_json(rel)
            if not isinstance(rec, DaySeal):
                raise LedgerError(f"{rel} is not a day seal")
            out.append(rec)
    return sorted(out, key=lambda s: s.day)


def seal_day(ledger: Ledger, day: date, clock: Clock) -> DaySeal:
    """Write `chain/day/X.json` linking to the previous seal. Idempotent."""
    rel = layout.day_seal_path(day)
    if ledger.exists(rel):
        existing = ledger.read_json(rel)
        assert isinstance(existing, DaySeal)
        return existing
    if clock.now().date() <= day:
        raise LedgerError(f"day {day} is not over yet (now {clock.now().isoformat()})")
    seals = day_seals(ledger)
    if seals and seals[-1].day > day:
        raise LedgerError(f"cannot seal {day}: a later day ({seals[-1].day}) is already sealed")
    prev = seals[-1].chain_sha256 if seals else layout.GENESIS_CHAIN
    files = day_files(ledger, day)
    seal = DaySeal(
        day=day,
        sealed_at=clock.now(),
        files=files,
        prev_chain_sha256=prev,
        chain_sha256=chain_hash(prev, files),
    )
    ledger.write_json(rel, seal)
    return seal


def seal_pending_days(ledger: Ledger, clock: Clock) -> list[DaySeal]:
    """Seal, in order, every finished day from the first ledger day that is not yet sealed.

    Days without files are sealed too, so the chain has no gaps.
    """
    days = [d for d in (layout.day_of(r) for r in ledger.list_files()) if d is not None]
    if not days:
        return []
    seals = day_seals(ledger)
    start = date.fromordinal(seals[-1].day.toordinal() + 1) if seals else min(days)
    yesterday = date.fromordinal(clock.now().date().toordinal() - 1)
    written = []
    for ordinal in range(start.toordinal(), yesterday.toordinal() + 1):
        written.append(seal_day(ledger, date.fromordinal(ordinal), clock))
    return written
