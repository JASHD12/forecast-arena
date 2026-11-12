"""Backtest reports: scores per forecaster and paired differences with day-block intervals.

Every number is computed here from backtest records (labelled "backtest"); nothing from
this module ever enters live scores (integrity rule I4).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from arena.backtest.harness import BacktestRecord
from arena.scoring.core import brier, log_score
from arena.scoring.stats import Interval, day_block_bootstrap, paired_brier_difference


@dataclass(frozen=True)
class Row:
    """Scores of one forecaster on the common questions."""

    forecaster_id: str
    n: int
    brier: Interval
    log: float


def common_records(
    records: Sequence[BacktestRecord], forecasters: Sequence[str]
) -> dict[str, dict[str, BacktestRecord]]:
    """{forecaster: {question_id: record}} restricted to resolved questions all answered."""
    by: dict[str, dict[str, BacktestRecord]] = {f: {} for f in forecasters}
    for r in records:
        if r.forecaster_id in by and r.outcome is not None:
            by[r.forecaster_id][r.question_id] = r
    common = set.intersection(*(set(v) for v in by.values())) if by else set()
    return {f: {q: v[q] for q in sorted(common)} for f, v in by.items()}


def score_rows(records: Sequence[BacktestRecord], forecasters: Sequence[str]) -> list[Row]:
    """Brier (with day-block interval) and log score per forecaster, common set."""
    by = common_records(records, forecasters)
    rows = []
    for f, items in by.items():
        if not items:
            continue
        rs = list(items.values())
        p, y = [r.probability for r in rs], [int(r.outcome or 0) for r in rs]
        terms = [(min(0.99, max(0.01, a)) - b) ** 2 for a, b in zip(p, y, strict=True)]
        rows.append(
            Row(f, len(rs), day_block_bootstrap([r.batch_date for r in rs], terms), log_score(p, y))
        )
        assert abs(rows[-1].brier.estimate - brier(p, y)) < 1e-9
    return rows


def paired(records: Sequence[BacktestRecord], a: str, b: str) -> Interval | None:
    """Brier(a) - Brier(b) on common questions (negative: a better)."""
    by = common_records(records, [a, b])
    qs = list(by[a])
    if not qs:
        return None
    return paired_brier_difference(
        [by[a][q].batch_date for q in qs],
        [by[a][q].probability for q in qs],
        [by[b][q].probability for q in qs],
        [int(by[a][q].outcome or 0) for q in qs],
    )


def markdown(
    title: str,
    records: Sequence[BacktestRecord],
    forecasters: Sequence[str],
    comparisons: Sequence[tuple[str, str]],
    notes: Sequence[str] = (),
) -> str:
    """A Markdown report; every figure computed from `records`."""
    rows = score_rows(records, forecasters)
    days = sorted({r.batch_date for r in records})
    lines = [f"# {title}", "", "**BACKTEST** (not part of the live record).", ""]
    if days:
        lines.append(f"Batches {days[0]} to {days[-1]} ({len(days)} batch days).")
    lines += ["", "| Forecaster | n | Brier | 95% interval | Log score |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r.forecaster_id} | {r.n} | {r.brier.estimate:.4f} | "
            f"[{r.brier.low:.4f}, {r.brier.high:.4f}] | {r.log:.4f} |"
        )
    lines += [
        "",
        "Paired Brier differences (negative = first is better), day-block "
        "bootstrap, 2000 replicates, fixed seed:",
        "",
        "| Comparison | Difference | 95% interval | Supported? |",
        "|---|---|---|---|",
    ]
    for a, b in comparisons:
        iv = paired(records, a, b)
        if iv is None:
            continue
        verdict = "yes" if iv.excludes_zero else "no (interval includes zero)"
        lines.append(
            f"| {a} - {b} | {iv.estimate:+.4f} | [{iv.low:+.4f}, {iv.high:+.4f}] | {verdict} |"
        )
    if notes:
        lines += ["", "Notes:", ""] + [f"- {n}" for n in notes]
    return "\n".join(lines) + "\n"
