"""Where does the model beat "same as last time"? Backtest Brier by slice (T220).

Average skill hides the regime, so this splits the walk-forward records of one backtest run
by question template, by month of the target day and by type of target day (weekday,
weekend, German national holiday), and compares two forecasters on exactly the same
questions with a paired, day-block bootstrap interval (negative difference: the first is
better). Everything is computed from stored backtest records; nothing is typed by hand
(I5) and nothing here touches the live record (I4).

Not covered: negative-price days. They need the realised price history, which the stored
records do not carry; adding them would mean re-reading the source data.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta

from arena.backtest.harness import BacktestRecord
from arena.calendar_de import is_holiday
from arena.scoring.stats import Interval, paired_brier_difference

MIN_QUESTIONS = 20  # smaller slices are listed but never described as a finding


@dataclass(frozen=True)
class SliceRow:
    """One slice: the first forecaster against the second on the same questions."""

    group: str
    name: str
    n: int
    days: int
    brier_a: float
    brier_b: float
    diff: Interval

    @property
    def verdict(self) -> str:
        """Plain wording of the paired difference."""
        if self.n < MIN_QUESTIONS:
            return "too few questions"
        if self.diff.high < 0:
            return "first is better"
        if self.diff.low > 0:
            return "second is better"
        return "no supported difference"


def _day_type(rec: BacktestRecord) -> str:
    target = rec.batch_date + timedelta(days=1)
    if is_holiday(target):
        return "holiday"
    return "weekend" if target.weekday() >= 5 else "weekday"


GROUPS: dict[str, Callable[[BacktestRecord], str]] = {
    "template": lambda r: r.template,
    "month": lambda r: (r.batch_date + timedelta(days=1)).strftime("%Y-%m"),
    "target day": _day_type,
}


def _pairs(
    records: Sequence[BacktestRecord], a: str, b: str
) -> list[tuple[BacktestRecord, BacktestRecord]]:
    by: dict[str, dict[str, BacktestRecord]] = defaultdict(dict)
    for r in records:
        if r.forecaster_id in (a, b) and r.outcome is not None:
            by[r.question_id][r.forecaster_id] = r
    return [(m[a], m[b]) for _, m in sorted(by.items()) if a in m and b in m]


def slice_rows(
    records: Sequence[BacktestRecord], a: str = "ml", b: str = "persistence"
) -> list[SliceRow]:
    """Every slice of every grouping, in a stable order (group, then name)."""
    pairs = _pairs(records, a, b)
    rows: list[SliceRow] = []
    for group, key in GROUPS.items():
        buckets: dict[str, list[tuple[BacktestRecord, BacktestRecord]]] = defaultdict(list)
        for pa, pb in pairs:
            buckets[key(pa)].append((pa, pb))
        for name in sorted(buckets):
            items = buckets[name]
            y = [pa.outcome or 0 for pa, _ in items]
            days = [pa.batch_date for pa, _ in items]
            diff = paired_brier_difference(
                days, [pa.probability for pa, _ in items], [pb.probability for _, pb in items], y
            )
            sq = lambda p, o: (min(0.99, max(0.01, p)) - o) ** 2  # noqa: E731
            rows.append(
                SliceRow(
                    group,
                    name,
                    len(items),
                    len(set(days)),
                    sum(sq(pa.probability, o) for (pa, _), o in zip(items, y, strict=True))
                    / len(items),
                    sum(sq(pb.probability, o) for (_, pb), o in zip(items, y, strict=True))
                    / len(items),
                    diff,
                )
            )
    return rows


def statement(rows: Sequence[SliceRow], a: str = "ml", b: str = "persistence") -> str:
    """One generated sentence on where the second forecaster is not worse than the first."""
    weak = [
        r
        for r in rows
        if r.n >= MIN_QUESTIONS and r.verdict in ("no supported difference", "second is better")
    ]
    if not weak:
        return (
            f"In every slice with at least {MIN_QUESTIONS} questions, `{a}` is better than "
            f"`{b}` with an interval that excludes zero."
        )
    names = ", ".join(f"{r.group} {r.name}" for r in weak)
    return (
        f"`{b}` is not clearly worse than `{a}` in: {names}. In the other slices with at "
        f"least {MIN_QUESTIONS} questions `{a}` is better with an interval that excludes zero."
    )


def markdown(
    records: Sequence[BacktestRecord], run_id: str, a: str = "ml", b: str = "persistence"
) -> str:
    """The model card text: statement plus one table per grouping."""
    rows = slice_rows(records, a, b)
    out = [
        f"# Backtest slices: where `{a}` beats `{b}` (power)",
        "",
        f"BACKTEST, not the live record (run `{run_id}`). Brier score per slice on the same "
        f"questions; difference = `{a}` minus `{b}` with a 95% day-block bootstrap interval "
        f"(negative: `{a}` is better). Slices under {MIN_QUESTIONS} questions are not described. "
        '"No supported difference" means the data cannot tell the two apart in that slice, not '
        "that they are equal; with this many slices, a few intervals will exclude zero by "
        "chance alone.",
        "",
        statement(rows, a, b),
    ]
    for group in GROUPS:
        out += [
            "",
            f"**By {group}**",
            "",
            f"| Slice | n | days | {a} Brier | {b} Brier | Difference | 95% interval | Verdict |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in (x for x in rows if x.group == group):
            verdict = r.verdict.replace("first is better", f"{a} better").replace(
                "second is better", f"{b} better"
            )
            out.append(
                f"| {r.name} | {r.n} | {r.days} | {r.brier_a:.4f} | {r.brier_b:.4f} | "
                f"{r.diff.estimate:+.4f} | [{r.diff.low:+.4f}, {r.diff.high:+.4f}] | {verdict} |"
            )
    return "\n".join(out) + "\n"
