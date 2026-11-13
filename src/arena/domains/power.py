"""Power domain (SPEC 7.1): German/Luxembourg day-ahead electricity prices from SMARD.

Target: delivery day D = B+1 in Europe/Berlin (23, 24 or 25 hours). Lock B 09:30 UTC.
Resolve after B 12:30 UTC. Grace 30 hours.

Interpretation choices (see docs/project/DECISIONS.md, "Power templates"):
- Thresholds are rounded to whole EUR/MWh (half-up). Comparisons use the values as
  published (two decimals); statistics of the day are rounded to two decimals first.
- Percentiles use linear interpolation between order statistics (the "type 7" rule).
- `evening_gt` is the mean of the three hourly prices starting 17:00, 18:00 and 19:00
  Europe/Berlin (the block 17:00-20:00).
- The trailing window ends at the latest complete day known at `asof` (normally B).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from itertools import pairwise
from typing import Any

from arena.domains.base import AsOfStore, is_degenerate, template_version_for, trailing_frequency
from arena.domains.power_history import PRICE_KEY, daily_from_store, daily_series
from arena.models import Evidence, Question, Resolution, Void, question_id_for
from arena.sources.smard import ATTRIBUTION, BERLIN, Point, berlin_day_hours

DOMAIN = "power"
ENTITY = "DE_LU"
#: Template versions: 1 = published on the batch morning, 2 = the evening before (T160).
LOCK = time(9, 30)
RESOLVE_AFTER = time(12, 30)
GRACE = timedelta(hours=30)
UNIT = "EUR/MWh"
SOURCE = (
    "SMARD (Bundesnetzagentur), filter 4169 'Day-ahead price Germany/Luxembourg', "
    "region DE, hourly: https://www.smard.de/app/chart_data/4169/DE/index_hour.json"
)
SOURCE_URL = "https://www.smard.de/app/chart_data/4169/DE/index_hour.json"
EVENING_HOURS = (17, 18, 19)


def r2(x: float) -> float:
    """Round half-up to two decimals (the precision SMARD publishes)."""
    return float(Decimal(repr(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def r0(x: float) -> float:
    """Round half-up to a whole EUR/MWh (natural unit for thresholds)."""
    return float(Decimal(repr(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def quantile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile (type 7). Needs at least one value."""
    xs = sorted(values)
    if not xs:
        raise ValueError("quantile of an empty sequence")
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def evening_values(day: date, values: Sequence[float]) -> list[float]:
    """Prices of the hours starting 17, 18, 19 Berlin time on `day`."""
    hours = berlin_day_hours(day)
    return [v for h, v in zip(hours, values, strict=True)
            if h.astimezone(BERLIN).hour in EVENING_HOURS]  # fmt: skip


def day_stats(day: date, values: Sequence[float]) -> dict[str, float]:
    """Daily statistics used by the templates, rounded to published precision."""
    return dict(_day_stats(day, tuple(values)))


@lru_cache(maxsize=16384)
def _day_stats(day: date, values: tuple[float, ...]) -> tuple[tuple[str, float], ...]:
    ev = evening_values(day, values)
    return (
        ("mean", r2(sum(values) / len(values))),
        ("max", r2(max(values))),
        ("min", r2(min(values))),
        ("spread", r2(max(values) - min(values))),
        ("evening", r2(sum(ev) / len(ev))),
    )


@dataclass(frozen=True)
class Template:
    """A threshold template: statistic, comparator, window and threshold rule."""

    name: str
    stat: str
    comparator: str
    window: int
    phrase: str
    rule: str


TEMPLATES: tuple[Template, ...] = (
    Template("mean_gt", "mean", "gt", 28, "have a daily mean price above",
             "Arithmetic mean of all hourly prices of D; YES if strictly greater than the "
             "threshold."),
    Template("max_gt", "max", "gt", 28, "have a highest hourly price above",
             "Maximum of the hourly prices of D; YES if strictly greater than the threshold."),
    Template("min_lt", "min", "lt", 60, "have a lowest hourly price below",
             "Minimum of the hourly prices of D; YES if strictly less than the threshold."),
    Template("spread_gt", "spread", "gt", 28,
             "have a spread (highest minus lowest hourly price) above",
             "Maximum minus minimum of the hourly prices of D; YES if strictly greater than "
             "the threshold."),
    Template("evening_gt", "evening", "gt", 28,
             "have a mean evening price (17:00-20:00 Europe/Berlin) above",
             "Mean of the three hourly prices starting 17:00, 18:00 and 19:00 Europe/Berlin "
             "on D; YES if strictly greater than the threshold."),
)  # fmt: skip
UP_WINDOW = 60
COMMON_RULE = (
    " Hourly day-ahead prices for Germany/Luxembourg in EUR/MWh as published by SMARD "
    "(two decimals) for the Europe/Berlin delivery day D, which has 23, 24 or 25 hours; "
    "the statistic is rounded half-up to two decimals before comparing. Void if any hour "
    "of D is still missing 30 hours after resolve_after."
)


def compare(value: float, comparator: str, threshold: float) -> bool:
    """Strict comparators (SPEC 7.0 ties rule); `ge` is inclusive."""
    if comparator == "gt":
        return value > threshold
    if comparator == "lt":
        return value < threshold
    if comparator == "ge":
        return value >= threshold
    raise ValueError(f"unknown comparator {comparator!r}")


def threshold_for(t: Template, stats: Sequence[dict[str, float]]) -> tuple[float, str]:
    """(threshold, rule description) from the window statistics."""
    xs = [s[t.stat] for s in stats]
    if t.name == "max_gt":
        return r0(quantile(xs, 0.60)), "60th percentile of daily maxima"
    if t.name == "min_lt":
        neg = sum(1 for x in xs if x < 0) / len(xs)
        if 0.10 <= neg <= 0.90:
            return 0.0, f"0 EUR/MWh (negative-price days were {neg:.0%} of the window)"
        return r0(quantile(xs, 0.40)), "40th percentile of daily minima"
    return r0(quantile(xs, 0.50)), f"median of daily {t.stat} values"


def _fmt_day(d: date) -> str:
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B %Y')}"


def _num(x: float) -> str:
    return f"{x:.0f}" if x == int(x) else f"{x:.2f}"


class PowerDomain:
    """Questions about tomorrow's day-ahead prices; data only through the as-of gateway.

    `store` holds price observations stamped with availability times (power_history).
    `evidence` maps a Berlin day to (source_url, sha256 of the SMARD chunk) for
    resolutions; without it the hash of the values themselves is used.
    """

    name = DOMAIN

    def __init__(
        self,
        store: AsOfStore,
        evidence: Callable[[date], tuple[str, str] | None] | None = None,
        on_skip: Callable[[str], None] | None = None,
    ) -> None:
        self.store = store
        self.evidence = evidence
        self.on_skip = on_skip or (lambda msg: None)
        self._known: dict[tuple[datetime, int, int], dict[date, list[float]]] = {}
        self._all: tuple[int, dict[date, list[float]]] | None = None

    # ----- generation --------------------------------------------------------------
    def known_days(self, asof: datetime, days: int) -> dict[date, list[float]]:
        """Complete Berlin days of prices available at `asof` (cached per store version)."""
        key = (asof, days, self.store.version)
        if key not in self._known:
            if len(self._known) > 512:
                self._known.clear()
            self._known[key] = daily_from_store(self.store, PRICE_KEY, asof, days)
        return self._known[key]

    def generate_questions(self, batch_date: date, asof: datetime) -> list[Question]:
        """Up to six questions about D = B+1; deterministic given B and the as-of data."""
        target = batch_date + timedelta(days=1)
        lock = datetime.combine(batch_date, LOCK, tzinfo=UTC)
        created = min(asof, lock)
        known = self.known_days(created, UP_WINDOW + 5)
        if not known:
            self.on_skip("power: no complete price days available")
            return []
        last = max(known)
        if last < batch_date - timedelta(days=2):
            self.on_skip(f"power: latest complete day {last} is stale")
            return []
        ordered = sorted(known)
        stats = {d: day_stats(d, known[d]) for d in ordered}
        out: list[Question] = []
        for t in TEMPLATES:
            window = [stats[d] for d in ordered[-t.window :]]
            if len(window) < t.window * 0.9:
                self.on_skip(f"power/{t.name}: only {len(window)} days in window")
                continue
            thr, how = threshold_for(t, window)
            freq = trailing_frequency([int(compare(s[t.stat], t.comparator, thr))
                                       for s in window])  # fmt: skip
            if is_degenerate(freq):
                self.on_skip(f"power/{t.name}: degenerate (trailing YES {freq:.2f})")
                continue
            hours = len(berlin_day_hours(target))
            text = (f"Will the German/Luxembourg day-ahead electricity price for "
                    f"{_fmt_day(target)} (Europe/Berlin delivery day, {hours} hours) "
                    f"{t.phrase} {_num(thr)} {UNIT}?")  # fmt: skip
            out.append(self._question(batch_date, target, created, lock, t.name, text,
                                      t.rule + COMMON_RULE, thr, t.comparator,
                                      {"stat": t.stat, "window_days": t.window,
                                       "window_end": last.isoformat(),
                                       "threshold_rule": how}, freq))  # fmt: skip
        out.extend(self._up_vs_today(batch_date, target, created, lock, ordered, stats))
        return out

    def _up_vs_today(self, batch_date: date, target: date, created: datetime, lock: datetime,
                     ordered: list[date], stats: dict[date, dict[str, float]]
                     ) -> list[Question]:  # fmt: skip
        if batch_date not in stats:
            self.on_skip(f"power/up_vs_today: mean for {batch_date} not available")
            return []
        ref = stats[batch_date]["mean"]
        window = ordered[-(UP_WINDOW + 1) :]
        ups = [int(stats[b]["mean"] > stats[a]["mean"]) for a, b in pairwise(window)
               if b - a == timedelta(days=1)]  # fmt: skip
        freq = trailing_frequency(ups)
        if is_degenerate(freq):
            self.on_skip(f"power/up_vs_today: degenerate (trailing YES {freq})")
            return []
        text = (f"Will the daily mean German/Luxembourg day-ahead electricity price for "
                f"{_fmt_day(target)} (Europe/Berlin delivery day) be higher than the daily "
                f"mean for {_fmt_day(batch_date)}, which was {_num(ref)} {UNIT}?")  # fmt: skip
        rule = (
            "Arithmetic mean of all hourly prices of D compared with the published mean "
            "of B stored in params.reference_mean; YES if strictly greater."
        )
        return [self._question(batch_date, target, created, lock, "up_vs_today", text,
                               rule + COMMON_RULE, None, "gt",
                               {"stat": "mean", "reference_day": batch_date.isoformat(),
                                "reference_mean": ref, "degeneracy_window_days": UP_WINDOW},
                               freq)]  # fmt: skip

    def _question(self, batch_date: date, target: date, created: datetime, lock: datetime,
                  template: str, text: str, rule: str, thr: float | None, comparator: str,
                  params: dict[str, Any], freq: float | None) -> Question:  # fmt: skip
        version = template_version_for(batch_date, created)
        return Question(
            question_id=question_id_for(DOMAIN, template, ENTITY, target, version),
            domain=DOMAIN,
            template=template,
            template_version=version,
            entity=ENTITY,
            text=text,
            batch_date=batch_date,
            target_date=target,
            created_at=created,
            lock_time=lock,
            resolve_after=datetime.combine(batch_date, RESOLVE_AFTER, tzinfo=UTC),
            resolution_source=SOURCE,
            resolution_rule=rule,
            threshold=thr,
            unit=UNIT,
            comparator=comparator,  # type: ignore[arg-type]
            params=params,
            base_rate_hint=None if freq is None else round(freq, 4),
            tags=["numeric", "power"],
        )

    # ----- context -----------------------------------------------------------------
    def context(self, question: Question, asof: datetime) -> dict[str, Any]:
        """Daily statistics of the last 28 known days and the hourly prices of the latest."""
        known = self.known_days(asof, 30)
        ordered = sorted(known)[-28:]
        latest = ordered[-1] if ordered else None
        return {
            "domain": DOMAIN,
            "asof": asof.isoformat(),
            "unit": UNIT,
            "attribution": ATTRIBUTION,
            "daily": [{"day": d.isoformat(), **day_stats(d, known[d])} for d in ordered],
            "latest_day": latest.isoformat() if latest else None,
            "latest_hourly": known[latest] if latest else [],
        }

    # ----- resolution --------------------------------------------------------------
    def all_days(self) -> dict[date, list[float]]:
        """Every complete Berlin day in the store, ignoring availability stamps.

        Only for training on days strictly before a cut-off and for resolution."""
        if self._all is None or self._all[0] != self.store.version:
            far = datetime.max.replace(tzinfo=UTC)
            pts = [Point(o.observed_at, o.value) for o in self.store.series(PRICE_KEY, far)]
            self._all = (self.store.version, daily_series(pts))
        return self._all[1]

    def observed(self, day: date) -> list[float] | None:
        """All hourly prices of Berlin day `day` that were fetched, or None if incomplete.

        Resolution uses every value the store holds (they were fetched live, so they
        exist), not the conservative availability stamps used for forecasting.
        """
        if self._all is None or self._all[0] != self.store.version:
            far = datetime.max.replace(tzinfo=UTC)
            pts = [Point(o.observed_at, o.value) for o in self.store.series(PRICE_KEY, far)]
            self._all = (self.store.version, daily_series(pts))
        return self._all[1].get(day)

    def resolve(self, question: Question, now: datetime) -> Resolution | Void | None:
        """None before resolve_after or while hours are missing; Void after grace."""
        if now < question.resolve_after:
            return None
        values = self.observed(question.target_date)
        if values is None:
            if now >= question.resolve_after + GRACE:
                return Void(question_id=question.question_id, reason_code="source_missing",
                            detail=f"not all hours of {question.target_date} published "
                                   f"by end of grace", voided_at=now)  # fmt: skip
            return None
        stats = day_stats(question.target_date, values)
        stat = str(question.params["stat"])
        value = stats[stat]
        if question.template == "up_vs_today":
            thr = float(question.params["reference_mean"])
        else:
            assert question.threshold is not None
            thr = question.threshold
        outcome = int(compare(value, question.comparator, thr))
        url, sha = self._evidence(question.target_date, values)
        return Resolution(
            question_id=question.question_id,
            outcome=outcome,  # type: ignore[arg-type]
            observed_value=value,
            resolved_at=now,
            evidence=Evidence(source_url=url, snapshot_sha256=sha,
                              values_used={"day": question.target_date.isoformat(),
                                           "hours": len(values), stat: value,
                                           "threshold": thr, "hourly": values}),
        )  # fmt: skip

    def _evidence(self, day: date, values: list[float]) -> tuple[str, str]:
        if self.evidence is not None:
            found = self.evidence(day)
            if found is not None:
                return found
        import hashlib
        import json

        blob = json.dumps({"day": day.isoformat(), "hourly": values}, sort_keys=True)
        return SOURCE_URL, hashlib.sha256(blob.encode()).hexdigest()

    def revised(self, question: Question, first: Resolution) -> bool:
        """True if the source now publishes different values than the first resolution."""
        values = self.observed(question.target_date)
        if values is None:
            return False
        return values != first.evidence.values_used.get("hourly")
