"""Templated, factual statements about the pre-registered hypotheses H1-H4 (SPEC 1, 11).

Every statement is computed from scored official-record forecasts. A hypothesis is called
supported (or contradicted) only when the relevant paired-difference interval excludes
zero; otherwise the statement says the evidence does not decide it. Below 30 official days
everything is "too early to tell". No causal language.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from arena.scoring.boards import MIN_DAYS
from arena.scoring.core import Scored
from arena.scoring.stats import Interval, paired_brier_difference

HYPOTHESES = {
    "H1": "On purely numeric domains (electricity prices, weather), the classical ML "
    "forecaster beats every LLM forecaster.",
    "H2": "On news-driven domains (Wikipedia attention), the LLM agent with tools beats the "
    "classical ML forecaster.",
    "H3": "Nobody beats the base rate on exchange-rate direction.",
    "H4": "The ensemble is at least as good as the best single forecaster.",
}
LLMS = ("llm_plain", "llm_context", "agent")
TOO_EARLY = "too early to tell"
SUPPORTED, CONTRADICTED, UNDECIDED = "supported", "contradicted", "not decided by the data"


@dataclass
class Comparison:
    """Brier(a) - Brier(b) on the questions both answered (negative: a is better)."""

    a: str
    b: str
    n: int
    interval: Interval

    def sentence(self) -> str:
        """Plain description; 'lower' only when the interval excludes zero."""
        iv = self.interval
        nums = f"{iv.estimate:+.4f} [{iv.low:+.4f}, {iv.high:+.4f}], n = {self.n}"
        if not iv.excludes_zero:
            return f"{self.a} vs {self.b}: no supported difference in Brier score ({nums})."
        better = self.a if iv.estimate < 0 else self.b
        return f"{self.a} vs {self.b}: {better} had the lower Brier score ({nums})."


@dataclass
class Finding:
    """One hypothesis with its computed status."""

    key: str
    text: str
    status: str
    comparisons: list[Comparison] = field(default_factory=list)
    note: str = ""


def compare(
    scored: Sequence[Scored],
    a: str,
    b: str,
    domains: set[str] | None = None,
    templates: set[str] | None = None,
) -> Comparison | None:
    """Paired comparison on common questions, or None without overlap."""

    def keep(s: Scored) -> bool:
        return (domains is None or s.domain in domains) and (
            templates is None or s.question_id.split("-")[1] in templates
        )

    fa = {s.question_id: s for s in scored if s.forecaster_id == a and keep(s)}
    fb = {s.question_id: s for s in scored if s.forecaster_id == b and keep(s)}
    qs = sorted(set(fa) & set(fb))
    if not qs:
        return None
    iv = paired_brier_difference(
        [fa[q].batch_date for q in qs],
        [fa[q].probability for q in qs],
        [fb[q].probability for q in qs],
        [fa[q].outcome for q in qs],
    )
    return Comparison(a, b, len(qs), iv)


def findings(scored: Sequence[Scored], official_days: int) -> list[Finding]:
    """H1-H4 from official-record forecasts."""
    if official_days < MIN_DAYS:
        return [
            Finding(
                k,
                t,
                TOO_EARLY,
                note=f"{official_days} official days so far; statements start at {MIN_DAYS}.",
            )
            for k, t in HYPOTHESES.items()
        ]
    out = []
    # H1: ml beats each LLM forecaster on power and weather.
    cs = [c for f in LLMS if (c := compare(scored, "ml", f, {"power", "weather"}))]
    out.append(_all_better("H1", cs, "ml"))
    # H2: agent beats ml on attention.
    c = compare(scored, "agent", "ml", {"attention"})
    out.append(_all_better("H2", [c] if c else [], "agent"))
    # H3: no forecaster beats base_rate on markets `up`.
    others = sorted({s.forecaster_id for s in scored if s.domain == "markets"} - {"base_rate"})
    cs = [c for f in others if (c := compare(scored, f, "base_rate", {"markets"}, {"up"}))]
    if not cs:
        out.append(Finding("H3", HYPOTHESES["H3"], UNDECIDED, note="no comparable forecasts"))
    else:
        beats = [c for c in cs if c.interval.excludes_zero and c.interval.estimate < 0]
        out.append(
            Finding(
                "H3",
                HYPOTHESES["H3"],
                CONTRADICTED if beats else SUPPORTED,
                cs,
                "Supported here means: no forecaster's advantage over the base "
                "rate has an interval that excludes zero.",
            )
        )
    # H4: ensemble not worse than the best single forecaster.
    singles = sorted({s.forecaster_id for s in scored} - {"ensemble"})
    cs = [c for f in singles if (c := compare(scored, "ensemble", f))]
    if not cs:
        out.append(Finding("H4", HYPOTHESES["H4"], UNDECIDED, note="the ensemble is not active"))
    else:
        worse = [c for c in cs if c.interval.excludes_zero and c.interval.estimate > 0]
        out.append(
            Finding(
                "H4",
                HYPOTHESES["H4"],
                CONTRADICTED if worse else SUPPORTED,
                cs,
                "Supported here means: no single forecaster is better than the "
                "ensemble with an interval that excludes zero.",
            )
        )
    return out


def _all_better(key: str, cs: list[Comparison], who: str) -> Finding:
    if not cs:
        return Finding(key, HYPOTHESES[key], UNDECIDED, note="no comparable forecasts yet")
    wins = [c.interval.excludes_zero and c.interval.estimate < 0 for c in cs]
    losses = [c.interval.excludes_zero and c.interval.estimate > 0 for c in cs]
    status = SUPPORTED if all(wins) else CONTRADICTED if any(losses) else UNDECIDED
    return Finding(key, HYPOTHESES[key], status, cs)


#: Pairs whose comparison decides a hypothesis, then fallbacks while `ml` is not live.
POWER_PAIRS = (
    ("ml", "llm_context"),
    ("agent", "ml"),
    ("llm_context", "base_rate"),
    ("agent", "base_rate"),
    ("persistence", "base_rate"),
)
EFFECTS = (0.01, 0.02)


def power_table(scored: Sequence[Scored]) -> list[dict[str, object]]:
    """For each available pair: days observed, the day-to-day spread of the paired Brier
    difference, and the days needed to detect a gap of 0.01 and 0.02 (80% power, 5%
    level). Planning numbers only; they decide nothing."""
    import statistics

    from arena.scoring.core import clip
    from arena.scoring.stats import days_needed

    by: dict[tuple[str, str], Scored] = {(s.question_id, s.forecaster_id): s for s in scored}
    qids = {s.question_id for s in scored}
    out: list[dict[str, object]] = []
    for a, b in POWER_PAIRS:
        per_day: dict[object, list[float]] = {}
        for q in qids:
            sa, sb = by.get((q, a)), by.get((q, b))
            if sa is None or sb is None:
                continue
            la = (clip(sa.probability) - sa.outcome) ** 2
            lb = (clip(sb.probability) - sb.outcome) ** 2
            per_day.setdefault(sa.batch_date, []).append(la - lb)
        if len(per_day) < 3:
            continue
        daily = [statistics.fmean(v) for _, v in sorted(per_day.items())]
        out.append(
            {
                "a": a,
                "b": b,
                "days": len(daily),
                "sd": round(statistics.stdev(daily), 4),
                "need": {e: days_needed(daily, e) for e in EFFECTS},
            }
        )
    return out
