"""Append-only ledger storage over a directory (SPEC 6).

Guarantees:
- Appends never change earlier bytes of a file (checked before the rename).
- Writes are atomic: a temp file in the same directory is fully written, fsynced and
  re-validated, then renamed over the target. A crash leaves the old file untouched.
- Every line is validated against the schema on write and on read, and must be canonical.
- Record ids are unique per family across the whole ledger; duplicates are refused.
- Files covered by a batch seal or a day seal are immutable.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ValidationError

from arena.ledger import layout
from arena.models import Record, canonical_json, parse_record


class LedgerError(Exception):
    """Any refused or invalid ledger operation."""


class Ledger:
    """A ledger rooted at a directory (usually `./_ledger`, a checkout of `ledger`)."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    # ----- paths -------------------------------------------------------------------
    def abspath(self, rel: str) -> Path:
        """Resolve a ledger-relative POSIX path, refusing anything that escapes the root."""
        pure = PurePosixPath(rel)
        if pure.is_absolute() or ".." in pure.parts or not pure.parts:
            raise LedgerError(f"bad ledger path: {rel!r}")
        return self.root.joinpath(*pure.parts)

    def exists(self, rel: str) -> bool:
        """True if the ledger file exists."""
        return self.abspath(rel).is_file()

    def list_files(self, prefix: str = "") -> list[str]:
        """All files under `prefix`, as sorted ledger-relative paths (git metadata skipped)."""
        base = self.abspath(prefix) if prefix else self.root
        if not base.exists():
            return []
        out = []
        for p in base.rglob("*"):
            if p.is_file() and ".git" not in p.relative_to(self.root).parts:
                out.append(p.relative_to(self.root).as_posix())
        return sorted(out)

    def read_bytes(self, rel: str) -> bytes:
        """Raw bytes of a ledger file."""
        return self.abspath(rel).read_bytes()

    # ----- reading -----------------------------------------------------------------
    def read(self, rel: str) -> list[Record]:
        """Parse and validate every line of a JSONL file. Missing file: empty list."""
        path = self.abspath(rel)
        if not path.exists():
            return []
        return list(_parse_lines(path.read_text(encoding="utf-8"), rel))

    def read_json(self, rel: str) -> Record:
        """Parse and validate a single-record JSON file."""
        text = self.abspath(rel).read_text(encoding="utf-8")
        records = list(_parse_lines(text, rel))
        if len(records) != 1:
            raise LedgerError(f"{rel}: expected exactly one record")
        return records[0]

    def iter_family(self, family: str) -> Iterator[tuple[str, Record]]:
        """Yield (path, record) for every record of a family, in path then line order."""
        if family not in layout.FAMILIES:
            raise LedgerError(f"unknown family {family!r}")
        for rel in self.list_files(family):
            if layout.family_of(rel) == family:
                for rec in self.read(rel):
                    yield rel, rec

    def ids(self, family: str) -> set[str]:
        """All record ids already present in a family."""
        return {rec.record_id for _, rec in self.iter_family(family)}

    # ----- sealing state -----------------------------------------------------------
    def sealed_reason(self, rel: str) -> str | None:
        """Why `rel` may no longer change, or None if it may be appended to."""
        day = layout.day_of(rel)
        if day is not None and self.exists(layout.day_seal_path(day)):
            return f"day {day} is sealed"
        if day is not None and rel in (layout.questions_path(day), layout.forecasts_path(day)):
            if self.exists(layout.batch_seal_path(day)):
                return f"batch {day} is sealed"
        return None

    # ----- writing -----------------------------------------------------------------
    def append(self, rel: str, records: Sequence[Record]) -> int:
        """Append records to a family JSONL file atomically. Returns the number written."""
        if not records:
            return 0
        family = layout.family_of(rel)
        if family is None:
            raise LedgerError(f"{rel} is not a record file")
        allowed = layout.FAMILIES[family]
        reason = self.sealed_reason(rel)
        if reason:
            raise LedgerError(f"refusing to append to {rel}: {reason}")
        existing_ids = self.ids(family)
        new_lines = []
        for rec in records:
            if not isinstance(rec, Record) or getattr(rec, "kind", None) not in allowed:
                raise LedgerError(f"{rel} accepts only {sorted(allowed)} records")
            if rec.record_id in existing_ids:
                raise LedgerError(f"duplicate id in {family}: {rec.record_id}")
            existing_ids.add(rec.record_id)
            new_lines.append(canonical_json(_revalidate(rec)))
        path = self.abspath(rel)
        old = path.read_bytes() if path.exists() else b""
        if old and not old.endswith(b"\n"):
            raise LedgerError(f"{rel} does not end with a newline; refusing to append")
        new = old + "".join(new_lines).encode("utf-8")
        self._atomic_write(path, new, prefix=old, rel=rel)
        return len(records)

    def write_json(self, rel: str, record: BaseModel) -> None:
        """Create a single-record JSON file (seal, manifest). Never overwrites."""
        if self.exists(rel):
            raise LedgerError(f"{rel} already exists; ledger files are never overwritten")
        reason = self.sealed_reason(rel)
        if reason:
            raise LedgerError(f"refusing to create {rel}: {reason}")
        data = canonical_json(record).encode("utf-8")
        self._atomic_write(self.abspath(rel), data, prefix=b"", rel=rel)

    def write_raw(self, rel: str, data: bytes) -> None:
        """Create a non-record file (snapshot, trace blob). Never overwrites."""
        if self.exists(rel):
            raise LedgerError(f"{rel} already exists; ledger files are never overwritten")
        reason = self.sealed_reason(rel)
        if reason:
            raise LedgerError(f"refusing to create {rel}: {reason}")
        self._atomic_write(self.abspath(rel), data, prefix=b"", rel=rel, validate=False)

    def _atomic_write(
        self, path: Path, data: bytes, *, prefix: bytes, rel: str, validate: bool = True
    ) -> None:
        if not data.startswith(prefix):  # defensive: appends must keep earlier bytes
            raise LedgerError(f"{rel}: write would change earlier bytes")
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            if validate:
                list(_parse_lines(tmp.read_text(encoding="utf-8"), rel))
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()


def _revalidate(rec: Record) -> Record:
    """Round-trip through JSON so model_copy(update=...) shortcuts cannot skip validation."""
    try:
        return parse_record(canonical_json(rec))
    except ValidationError as exc:
        raise LedgerError(f"invalid record: {exc}") from exc


def _parse_lines(text: str, rel: str) -> Iterable[Record]:
    if text and not text.endswith("\n"):
        raise LedgerError(f"{rel}: file does not end with a newline")
    for n, line in enumerate(text.splitlines(keepends=True), start=1):
        try:
            rec = parse_record(line)
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            raise LedgerError(f"{rel}:{n}: invalid record: {exc}") from exc
        if canonical_json(rec) != line:
            raise LedgerError(f"{rel}:{n}: line is not in canonical form")
        yield rec
