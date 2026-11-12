"""Walk-forward backtests through the real question, context and resolver code.

Integrity rule I4: backtest results live only under `backtests/`, every record carries
`label: "backtest"`, and the record type is not a ledger record, so the live ledger
refuses it (`Ledger.append` accepts only the ledger record kinds). The store also refuses
to write inside a directory that looks like a ledger checkout.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from arena.domains.base import Domain
from arena.forecasters.base import Forecaster, History, Instance
from arena.models import Forecast, Question, Resolution

LABEL: Literal["backtest"] = "backtest"
MORNING = time(5, 30)
FAR = datetime.max.replace(tzinfo=UTC)


class BacktestError(Exception):
    """Refused backtest operation."""


class BacktestRecord(BaseModel):
    """One backtest forecast with its outcome. Not a ledger record (different kind)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: Literal["backtest"] = LABEL
    kind: Literal["backtest_forecast"] = "backtest_forecast"
    run_id: str
    question_id: str
    domain: str
    template: str
    entity: str
    batch_date: date
    forecaster_id: str
    forecaster_version: str
    probability: float
    outcome: int | None
    meta: dict[str, Any] = {}


def looks_like_ledger(path: Path) -> bool:
    """True if `path` or a parent is a ledger checkout (has chain/ or questions/)."""
    for p in (path, *path.parents):
        if (p / "chain").is_dir() or (p / "questions").is_dir():
            return True
    return False


class BacktestStore:
    """Append-only JSONL files under `<root>/<run_id>/`, every line labelled backtest."""

    def __init__(self, root: Path) -> None:
        root = Path(root)
        if looks_like_ledger(root.resolve()):
            raise BacktestError(f"{root} is inside a ledger checkout; backtests stay apart")
        self.root = root

    def write(self, run_id: str, records: Sequence[BacktestRecord], meta: dict[str, Any]
              ) -> Path:  # fmt: skip
        """Write a run (records + meta). Runs are never overwritten."""
        d = self.root / run_id
        if d.exists():
            raise BacktestError(f"backtest run {run_id} already exists")
        d.mkdir(parents=True)
        lines = "".join(r.model_dump_json() + "\n" for r in records)
        (d / "forecasts.jsonl").write_text(lines, encoding="utf-8")
        (d / "meta.json").write_text(json.dumps({"label": LABEL, **meta}, indent=2,
                                                sort_keys=True, default=str) + "\n",
                                     encoding="utf-8")  # fmt: skip
        return d

    def read(self, run_id: str) -> list[BacktestRecord]:
        """Read a run back."""
        path = self.root / run_id / "forecasts.jsonl"
        return [BacktestRecord.model_validate_json(x) for x in path.read_text().splitlines()]


class IncrementalHistory:
    """History built from the walk-forward itself: an outcome is known once its question's
    resolve_after has passed (the conservative publication time)."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, str], dict[date, tuple[datetime, int]]] = {}

    def add(self, q: Question, r: Resolution) -> None:
        """Record a resolved question."""
        self._rows.setdefault((q.domain, q.template, q.entity), {})[q.target_date] = (
            q.resolve_after, r.outcome)  # fmt: skip

    def instances(self, domain: str, template: str, entity: str, before: date, asof: datetime
                  ) -> Sequence[Instance]:  # fmt: skip
        """See `History.instances`."""
        rows = self._rows.get((domain, template, entity), {})
        return [Instance(d, o) for d, (known, o) in sorted(rows.items())
                if d < before and known <= asof]  # fmt: skip


@dataclass
class BacktestResult:
    """Records plus bookkeeping."""

    run_id: str
    records: list[BacktestRecord] = field(default_factory=list)
    batches: int = 0
    skipped: dict[str, int] = field(default_factory=dict)


def batch_dates(first: date, last: date) -> Iterator[date]:
    """Every date from first to last inclusive."""
    d = first
    while d <= last:
        yield d
        d += timedelta(days=1)


def walk_forward(
    run_id: str,
    domain: Domain,
    make_forecasters: Callable[[History], Sequence[Forecaster]],
    first: date,
    last: date,
    *,
    warmup: int = 0,
) -> BacktestResult:
    """Replay batches first..last. Each morning sees only data available then; forecasts
    are scored against the domain's own resolver. The first `warmup` batches only feed the
    history (no forecasts recorded)."""
    hist = IncrementalHistory()
    forecasters = make_forecasters(hist)
    res = BacktestResult(run_id)
    pending: list[Question] = []
    for i, b in enumerate(batch_dates(first, last)):
        asof = datetime.combine(b, MORNING, tzinfo=UTC)
        still = []
        for q in pending:  # outcomes that became known by this morning feed the history
            r = domain.resolve(q, asof) if q.resolve_after <= asof else None
            if isinstance(r, Resolution):
                hist.add(q, r)
            elif r is None:
                still.append(q)
        pending = still
        qs = domain.generate_questions(b, asof)
        res.batches += 1
        for q in qs:
            pending.append(q)
            if i < warmup:
                continue
            ctx = domain.context(q, asof)
            final = domain.resolve(q, FAR)
            outcome = final.outcome if isinstance(final, Resolution) else None
            for f in forecasters:
                out = f.forecast(q, ctx, asof)
                if not isinstance(out, Forecast):
                    res.skipped[out.reason_code] = res.skipped.get(out.reason_code, 0) + 1
                    continue
                res.records.append(BacktestRecord(
                    run_id=run_id, question_id=q.question_id, domain=q.domain,
                    template=q.template, entity=q.entity, batch_date=b,
                    forecaster_id=f.forecaster_id, forecaster_version=out.forecaster_version,
                    probability=out.probability, outcome=outcome, meta=out.meta))  # fmt: skip
    return res
