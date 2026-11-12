"""`arena report cv`: headline numbers for a CV or interview, from the ledger only.

It prints what the record supports and nothing more: days live, resolved forecasts, the
official start, and each forecaster's headline Brier score with its interval. A comparison
is described as a win only when the board is past "too early to tell" and the paired
interval excludes zero; otherwise it says so explicitly.
"""

from __future__ import annotations

from datetime import date

from arena.ledger import Ledger
from arena.scoring.boards import TOO_EARLY, board, official
from arena.scoring.core import counts, load
from arena.site.build import official_start


def cv_lines(ledger: Ledger) -> list[str]:
    """The report, line by line."""
    rec = load(ledger)
    c = counts(rec)
    days = sorted({q.batch_date for q in rec.questions.values()})
    start_s = official_start(ledger)
    start = date.fromisoformat(start_s) if start_s else None
    off = official(rec.scored, start)
    off_days = len({s.batch_date for s in off})
    lines = [
        f"Days with questions: {len(days)}" + (f" ({days[0]} to {days[-1]})" if days else ""),
        f"Official record: {'since ' + start_s if start_s else 'not started (rehearsal only)'};"
        f" {off_days} official days",
        f"Questions: {c.questions}; resolved: {c.resolved}; voided: {sum(c.voided.values())};"
        f" forecasts: {c.forecasts}",
    ]
    b = board(off, "common", "overall", off_days)
    lines.append(
        f"Headline (common set, official record): {b.questions} questions, "
        f"forecasters {', '.join(b.forecasters) or 'none'}"
    )
    for r in b.rows:
        lines.append(
            f"  {r.forecaster_id}: Brier {r.brier.estimate:.4f} "
            f"[{r.brier.low:.4f}, {r.brier.high:.4f}] (n={r.n})"
        )
    if b.label == TOO_EARLY:
        lines.append(
            "Comparisons: too early to tell - no forecaster may be described as "
            "beating another yet."
        )
        return lines
    for r in b.rows:
        if r.vs_reference is None:
            continue
        if r.vs_reference.excludes_zero and r.vs_reference.estimate < 0:
            lines.append(
                f"  {r.forecaster_id} beat base_rate: Brier difference "
                f"{r.vs_reference.estimate:+.4f} [{r.vs_reference.low:+.4f}, "
                f"{r.vs_reference.high:+.4f}]"
            )
        else:
            lines.append(f"  {r.forecaster_id} vs base_rate: {r.verdict}")
    return lines
