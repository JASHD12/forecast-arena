"""Operational panels for the Status page (T080): missed days, LLM usage, parse failures
and source freshness. Everything is computed from the ledger alone."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from arena.ledger import Ledger, layout
from arena.ledger.manifest import manifests_for_day
from arena.ops.official import first_day
from arena.scoring.core import Record

#: Forecasters that call an LLM and can therefore fail to parse.
LLM_FORECASTERS = ("llm_plain", "llm_context", "llm_local", "agent", "agent_graph")


def missed_days(ledger: Ledger, today: date) -> list[date]:
    """Batch days from the first ledger day up to yesterday that have no batch seal
    (no forecasts were locked in for them)."""
    first = first_day(ledger)
    out: list[date] = []
    if first is None:
        return out
    d = first
    while d < today:
        if not ledger.exists(layout.batch_seal_path(d)):
            out.append(d)
        d += timedelta(days=1)
    return out


@dataclass(frozen=True)
class UsageDay:
    """LLM usage summed over every real run of one UTC day."""

    day: date
    requests: int
    input_tokens: int
    output_tokens: int

    @property
    def total(self) -> int:
        """Input plus output tokens."""
        return self.input_tokens + self.output_tokens


def llm_usage(ledger: Ledger, today: date, days: int = 7) -> list[UsageDay]:
    """Usage per day for the last `days` days (newest first), from the run manifests."""
    out = []
    for i in range(days):
        d = today - timedelta(days=i)
        req = inp = outp = 0
        for m in manifests_for_day(ledger, d):
            req += m.llm_usage.get("requests", 0)
            inp += m.llm_usage.get("input_tokens", 0)
            outp += m.llm_usage.get("output_tokens", 0)
        out.append(UsageDay(d, req, inp, outp))
    return out


@dataclass(frozen=True)
class ParseRow:
    """How often one LLM forecaster produced a usable probability."""

    forecaster_id: str
    forecasts: int
    parse_failures: int
    other_skips: int

    @property
    def failure_rate(self) -> float | None:
        """Parse failures as a share of attempts (forecasts + parse failures)."""
        n = self.forecasts + self.parse_failures
        return self.parse_failures / n if n else None


def parse_failures(rec: Record) -> list[ParseRow]:
    """Per LLM forecaster: forecasts, parse failures and other skips (not `not_sampled`)."""
    fc = Counter(f.forecaster_id for f in rec.forecasts)
    pf = Counter(s.forecaster_id for s in rec.skips if s.reason_code == "parse_failure")
    other = Counter(s.forecaster_id for s in rec.skips
                    if s.reason_code not in ("parse_failure", "not_sampled"))  # fmt: skip
    ids = [f for f in LLM_FORECASTERS if fc[f] or pf[f] or other[f]]
    return [ParseRow(f, fc[f], pf[f], other[f]) for f in ids]


@dataclass(frozen=True)
class Freshness:
    """When each domain last produced questions and resolutions."""

    domain: str
    last_batch: date
    last_resolved_at: datetime | None
    overdue: int

    def stale(self, now: datetime) -> bool:
        """True when the domain had no batch in the last two days."""
        return (now.date() - self.last_batch).days > 1


def source_freshness(rec: Record, now: datetime) -> list[Freshness]:
    """Per domain: latest batch, latest resolution time and the number of questions past
    `resolve_after` by more than a day that are still neither resolved nor void."""
    out = []
    for dom in sorted({q.domain for q in rec.questions.values()}):
        qs = [q for q in rec.questions.values() if q.domain == dom]
        res = [rec.resolutions[q.question_id].resolved_at for q in qs
               if q.question_id in rec.resolutions]  # fmt: skip
        overdue = sum(1 for q in qs if q.question_id not in rec.resolutions
                      and q.question_id not in rec.voids
                      and now - q.resolve_after > timedelta(days=1))  # fmt: skip
        out.append(Freshness(dom, max(q.batch_date for q in qs), max(res, default=None),
                             overdue))  # fmt: skip
    return out
