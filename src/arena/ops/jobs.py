"""The scheduled jobs: `morning` (questions, forecasts, seal) and `resolve` (outcomes, seals).

Both are idempotent: running a job twice for the same date and time writes nothing the
second time. The morning job enforces the lock time (integrity rule I1): a run at or after
the batch lock writes no questions and no forecasts and records the miss in its manifest.
A failing forecaster never aborts the batch: its failure is recorded as an `error` skip.
"""

from __future__ import annotations

import gzip
import json
import shutil
import tempfile
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from arena.clock import Clock
from arena.domains.base import Domain
from arena.forecasters.base import Forecaster
from arena.ledger import Ledger, layout
from arena.ledger.manifest import RunRecorder, run_manifest
from arena.ledger.seal import seal_batch, seal_pending_days
from arena.models import Forecast, Question, Resolution, Skip, Void

LOCK = time(9, 30)
#: How long after a first resolution the resolve job keeps checking for source revisions.
REVISION_WINDOW = timedelta(days=7)
MAX_DETAIL = 300


def batch_lock(batch: date, lock: time = LOCK) -> datetime:
    """The lock time shared by every question of a batch (SPEC 4)."""
    return datetime.combine(batch, lock, tzinfo=UTC)


@dataclass
class JobResult:
    """What a job did, for printing and tests."""

    job: str
    day: date
    written: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    late: bool = False

    def line(self) -> str:
        """One printable summary line."""
        parts = ", ".join(f"{k}={v}" for k, v in sorted(self.written.items())) or "nothing new"
        late = " LATE (after lock: no questions or forecasts written)" if self.late else ""
        return f"{self.job} {self.day}: {parts}{late}; {len(self.warnings)} warnings"


@contextmanager
def _maybe_dry(ledger: Ledger, dry_run: bool) -> Iterator[Ledger]:
    """In a dry run, work on a throwaway copy so the real ledger is never touched."""
    if not dry_run:
        yield ledger
        return
    with tempfile.TemporaryDirectory(prefix="arena-dry-") as tmp:
        copy = Path(tmp) / "ledger"
        if ledger.root.exists():
            shutil.copytree(ledger.root, copy, ignore=shutil.ignore_patterns(".git"))
        else:
            copy.mkdir()
        yield Ledger(copy)


def _short(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:MAX_DETAIL]


def _snapshot(ledger: Ledger, domain: str, batch: date, name: str, payload: Any) -> None:
    rel = f"{layout.snapshot_dir(domain, batch)}/{name}.json.gz"
    if ledger.exists(rel):
        return
    data = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ledger.write_raw(rel, gzip.compress(data, mtime=0))


def morning(
    ledger: Ledger,
    batch: date,
    clock: Clock,
    domains: Sequence[Domain],
    forecasters: Sequence[Forecaster],
    *,
    dry_run: bool = False,
    lock: time = LOCK,
    on_record: Callable[[RunRecorder], None] | None = None,
) -> JobResult:
    """Generate questions for `batch`, run every forecaster, snapshot inputs, seal."""
    res = JobResult("morning", batch)
    with _maybe_dry(ledger, dry_run) as led, run_manifest(led, "morning", batch, clock,
                                                         dry_run=dry_run) as rec:  # fmt: skip
        if on_record:
            on_record(rec)
        if led.exists(layout.batch_seal_path(batch)):
            rec.warn(f"batch {batch} already sealed; nothing to do")
            res.warnings = list(rec.warnings)
            return res
        deadline = batch_lock(batch, lock)
        now = clock.now()
        if now.date() != batch:
            rec.warn(f"batch {batch} is not today's UTC date ({now.date()}); refused")
            res.warnings = list(rec.warnings)
            return res
        if now >= deadline:
            res.late = True
            rec.count("late_runs")
            rec.warn(f"late run: {now.isoformat()} is at or after lock {deadline.isoformat()}")
            res.warnings = list(rec.warnings)
            return res

        qpath = layout.questions_path(batch)
        existing = [q for q in led.read(qpath) if isinstance(q, Question)]
        have_domains = {q.domain for q in existing}
        new_qs: list[Question] = []
        for dom in domains:
            if dom.name in have_domains:
                continue
            try:
                qs = dom.generate_questions(batch, clock.now())
            except Exception as exc:
                rec.warn(f"{dom.name}: question generation failed: {_short(exc)}")
                continue
            bad = [q for q in qs if q.lock_time != deadline or q.batch_date != batch]
            if bad:
                rec.warn(f"{dom.name}: generated questions with the wrong batch or lock")
                continue
            new_qs.extend(qs)
            rec.count(f"questions_{dom.name}", len(qs))
        if clock.now() >= deadline:
            res.late = True
            rec.warn("lock passed during question generation; nothing written")
            res.warnings = list(rec.warnings)
            return res
        if new_qs:
            res.written["questions"] = led.append(qpath, new_qs)
        all_qs = existing + new_qs

        for f in forecasters:  # e.g. the LLM forecasters draw their shared daily sample
            prepare = getattr(f, "prepare", None)
            if callable(prepare):
                try:
                    prepare(all_qs)
                except Exception as exc:
                    rec.warn(f"{f.forecaster_id}: prepare failed: {_short(exc)}")
        fpath = layout.forecasts_path(batch)
        done = {r.record_id for r in led.read(fpath)}
        by_domain = {d.name: d for d in domains}
        records: list[Forecast | Skip] = []
        contexts: dict[str, dict[str, Any]] = {}
        for q in all_qs:
            qdom = by_domain.get(q.domain)
            if qdom is None:
                continue
            asof = clock.now()
            try:
                ctx = qdom.context(q, asof)
            except Exception as exc:
                rec.warn(f"{q.question_id}: context failed: {_short(exc)}")
                ctx = {}
            contexts[q.question_id] = ctx
            for f in forecasters:
                fid = f"{q.question_id}::{f.forecaster_id}"
                if fid in done:
                    continue
                records.append(_run_forecaster(f, q, ctx, clock, rec))
                done.add(fid)
        if records:
            if clock.now() >= deadline:
                res.late = True
                rec.warn("lock passed while forecasting; forecasts discarded, not backdated")
                res.warnings = list(rec.warnings)
                return res
            res.written["forecasts"] = led.append(fpath, records)
            for r in records:
                rec.count("forecasts" if isinstance(r, Forecast) else f"skips_{r.reason_code}")
        traces = []
        for f in forecasters:
            lines = getattr(f, "trace_lines", None)
            if callable(lines):
                traces += [{"forecaster_id": f.forecaster_id, **x} for x in lines()]
        tpath = layout.agent_traces_path(batch)
        if traces and not led.exists(tpath):
            body = "".join(json.dumps(x, sort_keys=True, default=str) + "\n" for x in traces)
            led.write_raw(tpath, body.encode("utf-8"))
        for dom in domains:
            ctxs = {qid: c for qid, c in contexts.items() if qid.startswith(f"{dom.name}-")}
            if ctxs:
                _snapshot(led, dom.name, batch, "morning_context", ctxs)
        if all_qs and clock.now() < deadline:
            seal_batch(led, batch, clock)
            res.written["batch_seal"] = 1
        res.warnings = list(rec.warnings)
    return res


def _run_forecaster(
    f: Forecaster, q: Question, ctx: dict[str, Any], clock: Clock, rec: RunRecorder
) -> Forecast | Skip:
    """One forecast; any exception becomes an `error` skip, never a substitute number."""
    now = clock.now()
    try:
        out = f.forecast(q, ctx, now)
    except Exception as exc:
        rec.warn(f"{f.forecaster_id} failed on {q.question_id}: {_short(exc)}")
        try:
            version: str | None = f.version()
        except Exception:
            version = None
        return Skip(question_id=q.question_id, forecaster_id=f.forecaster_id,
                    forecaster_version=version, reason_code="error", detail=_short(exc),
                    created_at=now)  # fmt: skip
    if out.question_id != q.question_id or out.forecaster_id != f.forecaster_id:
        return Skip(question_id=q.question_id, forecaster_id=f.forecaster_id,
                    reason_code="error", detail="forecaster returned a record for another id",
                    created_at=now)  # fmt: skip
    return out


def open_questions(ledger: Ledger) -> tuple[list[Question], dict[str, Resolution]]:
    """Questions without a resolution or a (non-revision) void; first resolutions by id."""
    questions = [r for _, r in ledger.iter_family("questions") if isinstance(r, Question)]
    first: dict[str, Resolution] = {}
    closed: set[str] = set()
    for _, r in ledger.iter_family("resolutions"):
        if isinstance(r, Resolution):
            first.setdefault(r.question_id, r)
            closed.add(r.question_id)
        elif isinstance(r, Void) and r.reason_code != "source_revised":
            closed.add(r.question_id)
    return [q for q in questions if q.question_id not in closed], first


def resolve(
    ledger: Ledger,
    clock: Clock,
    domains: Sequence[Domain],
    *,
    dry_run: bool = False,
    revised: Callable[[Domain, Question, Resolution], bool] | None = None,
    after: Callable[[Ledger, RunRecorder], None] | None = None,
) -> JobResult:
    """Resolve whatever is resolvable now, record revisions, seal finished days.

    `after` runs inside the manifest (e.g. rescoring and the site build).
    """
    now = clock.now()
    res = JobResult("resolve", now.date())
    by_domain = {d.name: d for d in domains}
    with _maybe_dry(ledger, dry_run) as led, run_manifest(led, "resolve", now.date(), clock,
                                                         dry_run=dry_run) as rec:  # fmt: skip
        pending, first = open_questions(led)
        voided_ids = {r.record_id for _, r in led.iter_family("resolutions")}
        out: list[Resolution | Void] = []
        for q in pending:
            dom = by_domain.get(q.domain)
            if dom is None:
                continue
            try:
                r = dom.resolve(q, clock.now())
            except Exception as exc:
                rec.warn(f"{q.question_id}: resolve failed: {_short(exc)}")
                continue
            if r is not None:
                out.append(r)
                rec.count("resolutions" if isinstance(r, Resolution) else f"voids_{r.reason_code}")
        questions = {q.question_id: q for _, q in led.iter_family("questions")
                     if isinstance(q, Question)}  # fmt: skip
        check = revised or _default_revised
        for qid, r in first.items():
            rq = questions.get(qid)
            rdom = by_domain.get(rq.domain) if rq else None
            if rq is None or rdom is None or now - r.resolved_at > REVISION_WINDOW:
                continue
            if f"void::{qid}::source_revised" in voided_ids:
                continue
            try:
                if check(rdom, rq, r):
                    out.append(Void(question_id=qid, reason_code="source_revised",
                                    detail="source values changed after the first "
                                           "resolution; the first resolution is kept",
                                    voided_at=clock.now()))  # fmt: skip
                    rec.count("revisions")
            except Exception as exc:
                rec.warn(f"{qid}: revision check failed: {_short(exc)}")
        if out:
            res.written["resolutions"] = led.append(layout.resolutions_path(now.date()), out)
        sealed = seal_pending_days(led, clock)
        if sealed:
            res.written["day_seals"] = len(sealed)
        if after is not None:
            after(led, rec)
        res.warnings = list(rec.warnings)
    return res


def _default_revised(dom: Domain, q: Question, r: Resolution) -> bool:
    fn = getattr(dom, "revised", None)
    return bool(fn(q, r)) if callable(fn) else False
