"""`arena ledger verify`: recompute seals and the chain and check forecast-before-lock."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from arena.ledger import layout
from arena.ledger.seal import batch_files, chain_hash, day_files, file_sha256
from arena.ledger.store import Ledger, LedgerError
from arena.models import BatchSeal, DaySeal, Forecast, Question


@dataclass
class VerifyReport:
    """Result of a verification: empty `errors` means the ledger passed."""

    errors: list[str] = field(default_factory=list)
    checked_files: int = 0
    batch_seals: int = 0
    day_seals: int = 0
    forecasts: int = 0

    @property
    def ok(self) -> bool:
        """True when no error was found."""
        return not self.errors

    def summary(self) -> str:
        """One-paragraph human summary."""
        head = "PASS" if self.ok else f"FAIL ({len(self.errors)} problems)"
        stats = (
            f"{self.checked_files} files, {self.batch_seals} batch seals, "
            f"{self.day_seals} day seals, {self.forecasts} forecasts checked"
        )
        return "\n".join([f"ledger verify: {head}: {stats}", *(f"  - {e}" for e in self.errors)])


def verify(ledger: Ledger) -> VerifyReport:
    """Run every offline check of SPEC 6 and return a report (never raises on tampering)."""
    rep = VerifyReport()
    files = ledger.list_files()
    rep.checked_files = len(files)

    # 1. Every record file parses, is canonical, and ids are unique per family.
    seen: dict[str, dict[str, str]] = {f: {} for f in layout.FAMILIES}
    questions: dict[str, Question] = {}
    forecasts: list[tuple[str, Forecast]] = []
    for rel in files:
        if rel.split("/")[-1].startswith(".tmp-"):
            rep.errors.append(f"{rel}: leftover temp file")
            continue
        fam = layout.family_of(rel)
        try:
            if fam is not None:
                records = ledger.read(rel)
            elif rel.endswith(".json") and rel.startswith(("runs/", "chain/")):
                records = [ledger.read_json(rel)]
            else:
                continue
        except LedgerError as exc:
            rep.errors.append(str(exc))
            continue
        for rec in records:
            if fam is not None:
                if rec.kind not in layout.FAMILIES[fam]:
                    rep.errors.append(f"{rel}: {rec.kind} record in {fam} file")
                prior = seen[fam].get(rec.record_id)
                if prior:
                    rep.errors.append(f"{rel}: duplicate id {rec.record_id} (first in {prior})")
                seen[fam][rec.record_id] = rel
            if isinstance(rec, Question):
                questions[rec.question_id] = rec
            elif isinstance(rec, Forecast):
                forecasts.append((rel, rec))

    # 2. Forecast before truth.
    for rel, fc in forecasts:
        rep.forecasts += 1
        q = questions.get(fc.question_id)
        if q is None:
            rep.errors.append(f"{rel}: forecast {fc.forecast_id} for unknown question")
        elif not fc.created_at < q.lock_time:
            rep.errors.append(
                f"{rel}: forecast {fc.forecast_id} created at {fc.created_at.isoformat()} "
                f"is not before lock {q.lock_time.isoformat()}"
            )

    # 3. Batch seals.
    for rel in files:
        batch = layout.batch_seal_date(rel)
        if batch is None:
            continue
        rep.batch_seals += 1
        try:
            seal = ledger.read_json(rel)
        except LedgerError:
            continue  # already reported above
        if not isinstance(seal, BatchSeal) or seal.batch_date != batch:
            rep.errors.append(f"{rel}: not a batch seal for {batch}")
            continue
        _compare(rep, f"batch seal {batch}", seal.files, batch_files(ledger, batch))

    # 4. Day seals and the chain.
    seals: list[DaySeal] = []
    for rel in files:
        day = layout.day_seal_date(rel)
        if day is None:
            continue
        try:
            seal = ledger.read_json(rel)
        except LedgerError:
            continue
        if not isinstance(seal, DaySeal) or seal.day != day:
            rep.errors.append(f"{rel}: not a day seal for {day}")
            continue
        seals.append(seal)
    seals.sort(key=lambda s: s.day)
    rep.day_seals = len(seals)
    prev = layout.GENESIS_CHAIN
    for i, seal in enumerate(seals):
        if i and seal.day.toordinal() != seals[i - 1].day.toordinal() + 1:
            rep.errors.append(f"day seals have a gap between {seals[i - 1].day} and {seal.day}")
        if seal.prev_chain_sha256 != prev:
            rep.errors.append(f"day seal {seal.day}: prev_chain_sha256 does not link to the chain")
        if chain_hash(seal.prev_chain_sha256, seal.files) != seal.chain_sha256:
            rep.errors.append(f"day seal {seal.day}: chain_sha256 does not match its files")
        _compare(rep, f"day seal {seal.day}", seal.files, day_files(ledger, seal.day))
        prev = seal.chain_sha256
    if seals:
        first_day = min((d for d in map(layout.day_of, files) if d), default=seals[0].day)
        if first_day < seals[0].day:
            rep.errors.append(f"files dated {first_day} precede the first day seal")
    return rep


def _compare(rep: VerifyReport, label: str, sealed: dict[str, str], now: dict[str, str]) -> None:
    for path in sorted(set(sealed) | set(now)):
        if path not in now:
            rep.errors.append(f"{label}: sealed file {path} is missing")
        elif path not in sealed:
            rep.errors.append(f"{label}: file {path} was added after the seal")
        elif sealed[path] != now[path]:
            rep.errors.append(f"{label}: {path} changed after the seal")


def first_unsealed(ledger: Ledger) -> date | None:
    """Earliest dated file whose day has no seal (diagnostic helper)."""
    days = sorted({d for d in map(layout.day_of, ledger.list_files()) if d})
    for d in days:
        if not ledger.exists(layout.day_seal_path(d)):
            return d
    return None


__all__ = ["VerifyReport", "file_sha256", "first_unsealed", "verify"]
