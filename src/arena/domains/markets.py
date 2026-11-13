"""Markets domain (SPEC 7.4): ECB reference rates EUR/USD and EUR/JPY, the control domain.

F0 = the fixing published on the batch day B, F1 = the next fixing after B. Both are
unknown at the 09:30 UTC lock (fixings are published around 16:00 CET). Questions are
created only when B is a publication day. Target date = the day of F1. Resolve after
16:00 UTC on that day. Grace 96 hours.

Interpretation (docs/project/DECISIONS.md "Markets templates"): log returns from the published
four-decimal rates, rounded to 6 decimals before comparing; `absmove_gt` threshold = the
median absolute log return between consecutive fixings over the last 60 returns, rounded
half-up to 0.0001; `up` degeneracy uses the last 250 returns.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise
from typing import Any

from arena.domains.base import (
    AsOfStore,
    Observation,
    is_degenerate,
    template_version_for,
    trailing_frequency,
)
from arena.models import Evidence, Question, Resolution, Void, question_id_for
from arena.sources.ecb import (
    ATTRIBUTION,
    fixing_available_at,
    is_publication_day,
    next_publication_day,
)

DOMAIN = "markets"
#: Template versions: 1 = published on the batch morning, 2 = the evening before (T160).
PAIRS = ("USD", "JPY")
LOCK = time(9, 30)
RESOLVE_AFTER = time(16, 0)
GRACE = timedelta(hours=96)
ABS_WINDOW = 60
UP_WINDOW = 250
SOURCE_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.{ccy}.EUR.SP00.A"


def key(ccy: str) -> str:
    """Store key of a currency's fixings."""
    return f"ecb:{ccy}"


def logret(f0: float, f1: float) -> float:
    """ln(F1/F0) rounded to 6 decimals."""
    return round(math.log(f1 / f0), 6)


def bp(x: float) -> float:
    """Round half-up to 0.0001."""
    return float(Decimal(repr(x)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def add_rates(store: AsOfStore, rates: dict[str, dict[date, float]]) -> None:
    """Fixings stamped with their conservative availability time."""
    for ccy, series in rates.items():
        for d, v in series.items():
            obs_at = datetime.combine(d, time(0), tzinfo=UTC)
            store.add(Observation(fixing_available_at(d), obs_at, key(ccy), v))


class MarketsDomain:
    """Questions about the next ECB fixing relative to today's."""

    name = DOMAIN

    def __init__(
        self,
        store: AsOfStore,
        evidence: tuple[str, str] | None = None,
        on_skip: Callable[[str], None] | None = None,
    ) -> None:
        self.store = store
        self.evidence = evidence
        self.on_skip = on_skip or (lambda msg: None)

    def fixings(self, ccy: str, asof: datetime) -> dict[date, float]:
        """Fixings known at `asof`, by day."""
        return {o.observed_at.date(): o.value for o in self.store.series(key(ccy), asof)
                if o.value is not None}  # fmt: skip

    def generate_questions(self, batch_date: date, asof: datetime) -> list[Question]:
        """`absmove_gt` and `up` per pair; none unless B is a publication day."""
        if not is_publication_day(batch_date):
            self.on_skip(f"markets: {batch_date} is not an ECB publication day")
            return []
        target = next_publication_day(batch_date)
        lock = datetime.combine(batch_date, LOCK, tzinfo=UTC)
        created = min(asof, lock)
        out: list[Question] = []
        for ccy in PAIRS:
            fx = self.fixings(ccy, created)
            days = sorted(d for d in fx if d < batch_date)
            if not days or days[-1] < batch_date - timedelta(days=7):
                self.on_skip(f"markets/{ccy}: fixings missing or stale")
                continue
            rets = [logret(fx[a], fx[b]) for a, b in pairwise(days)]
            pair = f"EUR_{ccy}"
            recent = rets[-ABS_WINDOW:]
            if len(recent) == ABS_WINDOW:
                thr = bp(statistics.median(abs(r) for r in recent))
                freq = trailing_frequency([int(abs(r) > thr) for r in recent])
                if is_degenerate(freq) or thr <= 0:
                    self.on_skip(f"markets/absmove_gt/{ccy}: degenerate ({freq})")
                else:
                    text = (f"Will the absolute log change of the ECB euro reference rate "
                            f"EUR/{ccy} from the fixing of {batch_date.isoformat()} to the next "
                            f"fixing ({target.isoformat()}) exceed {thr:.4f}, that is "
                            f"|ln(F1/F0)| > {thr:.4f}?")  # fmt: skip
                    rule = (
                        "F0 = ECB reference rate (units of the currency per euro, as "
                        "published, four decimals) on the batch date; F1 = the next "
                        "published fixing. YES if |ln(F1/F0)|, rounded to 6 decimals, is "
                        "strictly greater than the threshold."
                    )
                    out.append(self._q("absmove_gt", pair, ccy, batch_date, target, created,
                                       lock, text, rule, thr, "log return", "gt",
                                       {"window_fixings": ABS_WINDOW}, freq))  # fmt: skip
            else:
                self.on_skip(f"markets/absmove_gt/{ccy}: only {len(recent)} returns")
            ups = [int(r > 0) for r in rets[-UP_WINDOW:]]
            freq = trailing_frequency(ups)
            if len(ups) < UP_WINDOW or is_degenerate(freq):
                self.on_skip(f"markets/up/{ccy}: insufficient or degenerate history")
                continue
            text = (f"Will the ECB euro reference rate EUR/{ccy} published on {target.isoformat()} "
                    f"be higher than the one published on {batch_date.isoformat()}?")  # fmt: skip
            rule = (
                "F0 = ECB reference rate on the batch date, F1 = the next published fixing "
                "(four decimals, units of the currency per euro); YES if F1 > F0 "
                "(an equal rate is NO)."
            )
            out.append(self._q("up", pair, ccy, batch_date, target, created, lock, text, rule,
                               None, "rate", "gt", {"degeneracy_window_fixings": UP_WINDOW},
                               freq))  # fmt: skip
        return out

    def _q(self, template: str, pair: str, ccy: str, batch_date: date, target: date,
           created: datetime, lock: datetime, text: str, rule: str, thr: float | None,
           unit: str, comparator: str, params: dict[str, Any], freq: float | None
           ) -> Question:  # fmt: skip
        common = (
            " F0 must be the fixing of the batch date itself. Void if F0 or F1 is still "
            "missing 96 hours after resolve_after."
        )
        version = template_version_for(batch_date, created)
        return Question(
            question_id=question_id_for(DOMAIN, template, pair, target, version),
            domain=DOMAIN,
            template=template,
            template_version=version,
            entity=pair,
            text=text,
            batch_date=batch_date,
            target_date=target,
            created_at=created,
            lock_time=lock,
            resolve_after=datetime.combine(target, RESOLVE_AFTER, tzinfo=UTC),
            resolution_source=SOURCE_URL.format(ccy=ccy),
            resolution_rule=rule + common,
            threshold=thr,
            unit=unit,
            comparator=comparator,  # type: ignore[arg-type]
            params={"currency": ccy, "f0_day": batch_date.isoformat(),
                    "f1_day": target.isoformat(), **params},
            base_rate_hint=None if freq is None else round(freq, 4),
            tags=["markets", "control"],
        )  # fmt: skip

    def context(self, question: Question, asof: datetime) -> dict[str, Any]:
        """The last 60 known fixings of the pair."""
        ccy = str(question.params["currency"])
        fx = self.fixings(ccy, asof)
        last = sorted(fx)[-60:]
        return {
            "domain": DOMAIN,
            "asof": asof.isoformat(),
            "attribution": ATTRIBUTION,
            "pair": question.entity,
            "fixings": [{"day": d.isoformat(), "rate": fx[d]} for d in last],
        }

    def resolve(self, question: Question, now: datetime) -> Resolution | Void | None:
        """Needs both F0 (the batch day's fixing) and F1 (the target day's)."""
        if now < question.resolve_after:
            return None
        ccy = str(question.params["currency"])
        far = datetime.max.replace(tzinfo=UTC)
        fx = self.fixings(ccy, far)
        f0 = fx.get(date.fromisoformat(str(question.params["f0_day"])))
        f1 = fx.get(question.target_date)
        if f0 is None or f1 is None:
            if now >= question.resolve_after + GRACE:
                return Void(question_id=question.question_id, reason_code="source_missing",
                            detail="F0 or F1 not published by the end of grace",
                            voided_at=now)  # fmt: skip
            return None
        r = logret(f0, f1)
        if question.template == "absmove_gt":
            assert question.threshold is not None
            value, outcome = abs(r), int(abs(r) > question.threshold)
        else:
            value, outcome = f1, int(f1 > f0)
        url, sha = self.evidence or (SOURCE_URL.format(ccy=ccy), "0" * 64)
        return Resolution(
            question_id=question.question_id,
            outcome=outcome,  # type: ignore[arg-type]
            observed_value=value,
            resolved_at=now,
            evidence=Evidence(source_url=url, snapshot_sha256=sha,
                              values_used={"f0": f0, "f1": f1, "log_return": r}),
        )  # fmt: skip

    def revised(self, question: Question, first: Resolution) -> bool:
        """True if the published F0 or F1 changed after the first resolution."""
        ccy = str(question.params["currency"])
        fx = self.fixings(ccy, datetime.max.replace(tzinfo=UTC))
        f0 = fx.get(date.fromisoformat(str(question.params["f0_day"])))
        f1 = fx.get(question.target_date)
        used = first.evidence.values_used
        return (f0, f1) != (used.get("f0"), used.get("f1"))


def markets_domain_from_rates(rates: dict[str, dict[date, float]], url: str, sha: str,
                              on_skip: Callable[[str], None] | None = None
                              ) -> MarketsDomain:  # fmt: skip
    """Build a domain from a fetched ECB response."""
    store = AsOfStore()
    add_rates(store, rates)
    return MarketsDomain(store, evidence=(url, sha), on_skip=on_skip)
