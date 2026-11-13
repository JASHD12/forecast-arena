"""Crypto domain (owner request 2026-11-12, DECISIONS.md "Crypto domain"): daily moves of
five major coins in USD, from CoinGecko's daily prices.

P0 = the CoinGecko price stamped 00:00 UTC on the target day D (= B+1), P1 = the price
stamped 00:00 UTC on D+1. Both are unknown at the 09:30 UTC lock on B. The move of day D
is r = ln(P1/P0), rounded to 6 decimals.

- `up`: YES if r > 0 (an unchanged price is NO). Degeneracy window: 250 days.
- `bigmove`: YES if |r| > T, T = median |r| over the last 60 known days, rounded half-up
  to 0.001 (0.1 %).

Resolve after D+1 01:00 UTC (the 00:00 point is published after 00:35 UTC). CoinGecko may
revise a value for up to 2 days; later changes are recorded as revisions, like SMARD's.
Grace 72 hours, then void. This is a research benchmark, not advice (SPEC 2, S12).
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Callable, Mapping
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
from arena.sources.coingecko import ATTRIBUTION, available_at

DOMAIN = "crypto"
#: Template versions: 1 = published on the batch morning, 2 = the evening before (T160).
#: CoinGecko id -> display name. Fixed list; changing it needs a decision record.
COINS: dict[str, str] = {
    "bitcoin": "Bitcoin",
    "ethereum": "Ethereum",
    "solana": "Solana",
    "ripple": "XRP",
    "binancecoin": "BNB",
}
LOCK = time(9, 30)
RESOLVE_AFTER = time(1, 0)
GRACE = timedelta(hours=72)
ABS_WINDOW = 60
UP_WINDOW = 250
CONTEXT_DAYS = 60
SOURCE_URL = "https://api.coingecko.com/api/v3/coins/{coin}/market_chart"


def key(coin: str) -> str:
    """Store key of a coin's daily prices."""
    return f"cg:{coin}"


def logret(p0: float, p1: float) -> float:
    """ln(P1/P0) rounded to 6 decimals."""
    return round(math.log(p1 / p0), 6)


def to_thousandth(x: float) -> float:
    """Round half-up to 0.001."""
    return float(Decimal(repr(x)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def add_prices(store: AsOfStore, prices: Mapping[str, Mapping[date, float]]) -> None:
    """Daily prices stamped with their conservative availability time."""
    for coin, rows in prices.items():
        for d, p in rows.items():
            obs_at = datetime.combine(d, time(0), tzinfo=UTC)
            store.add(Observation(available_at(d), obs_at, key(coin), p))


def _fmt_day(d: date) -> str:
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B %Y')}"


class CryptoDomain:
    """Questions about tomorrow's move of five major crypto coins."""

    name = DOMAIN

    def __init__(
        self,
        store: AsOfStore,
        evidence: Mapping[str, tuple[str, str]] | None = None,
        on_skip: Callable[[str], None] | None = None,
    ) -> None:
        self.store = store
        self.evidence = dict(evidence or {})
        self.on_skip = on_skip or (lambda msg: None)

    def prices(self, coin: str, asof: datetime) -> dict[date, float]:
        """{UTC day: price} known at `asof`."""
        out = {}
        for o in self.store.series(key(coin), asof):
            if o.value is not None:
                out[o.observed_at.date()] = float(o.value)
        return dict(sorted(out.items()))

    @staticmethod
    def returns(px: Mapping[date, float]) -> list[float]:
        """Daily log returns between consecutive days (gaps are skipped)."""
        days = sorted(px)
        return [logret(px[a], px[b]) for a, b in pairwise(days) if (b - a) == timedelta(days=1)]

    def generate_questions(self, batch_date: date, asof: datetime) -> list[Question]:
        """`up` and `bigmove` for each coin; deterministic given B and the data."""
        target = batch_date + timedelta(days=1)
        lock = datetime.combine(batch_date, LOCK, tzinfo=UTC)
        created = min(asof, lock)
        out: list[Question] = []
        for coin, name in COINS.items():
            px = self.prices(coin, created)
            if not px or max(px) < batch_date - timedelta(days=2):
                self.on_skip(f"crypto/{coin}: prices missing or stale")
                continue
            rets = self.returns(px)
            recent = rets[-ABS_WINDOW:]
            if len(recent) >= ABS_WINDOW:
                thr = to_thousandth(statistics.median(abs(r) for r in recent))
                freq = trailing_frequency([int(abs(r) > thr) for r in recent])
                if thr <= 0 or is_degenerate(freq):
                    self.on_skip(f"crypto/bigmove/{coin}: degenerate ({freq})")
                else:
                    pct = f"{thr * 100:.1f}"
                    text = (f"Will the price of {name} in US dollars (CoinGecko) move by more "
                            f"than {pct} % (up or down) over {_fmt_day(target)} (UTC), "
                            f"from 00:00 UTC that day to 00:00 UTC the next day?")  # fmt: skip
                    rule = (
                        "P0 = CoinGecko USD price stamped 00:00 UTC on D, P1 = the price "
                        "stamped 00:00 UTC on D+1 (daily market_chart); YES if "
                        "|ln(P1/P0)| rounded to 6 decimals is strictly greater than the "
                        "threshold (a log return)."
                    )
                    out.append(self._q(coin, name, "bigmove", batch_date, target, created, lock,
                                       text, rule, thr, "log return",
                                       {"window_days": ABS_WINDOW,
                                        "threshold_rule": "median |daily log return| of the "
                                        "last 60 known days, rounded to 0.001"}, freq))  # fmt: skip
            else:
                self.on_skip(f"crypto/bigmove/{coin}: only {len(recent)} returns")
            ups = [int(r > 0) for r in rets[-UP_WINDOW:]]
            freq = trailing_frequency(ups)
            if len(ups) < UP_WINDOW or is_degenerate(freq):
                self.on_skip(f"crypto/up/{coin}: insufficient or degenerate history")
                continue
            text = (f"Will the price of {name} in US dollars (CoinGecko) be higher at 00:00 UTC "
                    f"on {_fmt_day(target + timedelta(days=1))} than at 00:00 UTC on "
                    f"{_fmt_day(target)}?")  # fmt: skip
            rule = (
                "P0 = CoinGecko USD price stamped 00:00 UTC on D, P1 = the price stamped "
                "00:00 UTC on D+1 (daily market_chart); YES if ln(P1/P0) rounded to 6 "
                "decimals is strictly greater than 0 (unchanged is NO)."
            )
            out.append(self._q(coin, name, "up", batch_date, target, created, lock, text, rule,
                               None, "USD", {"degeneracy_window_days": UP_WINDOW},
                               freq))  # fmt: skip
        return out

    def _q(self, coin: str, name: str, template: str, batch_date: date, target: date,
           created: datetime, lock: datetime, text: str, rule: str, thr: float | None,
           unit: str, params: dict[str, Any], freq: float | None) -> Question:  # fmt: skip
        common = (
            " CoinGecko may revise a price for up to 2 days; later changes are recorded as "
            "revisions. Void if P0 or P1 is still missing 72 hours after resolve_after."
        )
        version = template_version_for(batch_date, created)
        return Question(
            question_id=question_id_for(DOMAIN, template, coin, target, version),
            domain=DOMAIN,
            template=template,
            template_version=version,
            entity=coin,
            text=text,
            batch_date=batch_date,
            target_date=target,
            created_at=created,
            lock_time=lock,
            resolve_after=datetime.combine(target + timedelta(days=1), RESOLVE_AFTER, tzinfo=UTC),
            resolution_source=SOURCE_URL.format(coin=coin) + "?vs_currency=usd&interval=daily",
            resolution_rule=rule + common,
            threshold=thr,
            unit=unit,
            comparator="gt",
            params={
                "coin": coin,
                "coin_name": name,
                "p0_day": target.isoformat(),
                "p1_day": (target + timedelta(days=1)).isoformat(),
                **params,
            },
            base_rate_hint=None if freq is None else round(freq, 4),
            tags=["crypto", "markets"],
        )

    def context(self, question: Question, asof: datetime) -> dict[str, Any]:
        """The last 60 known daily prices of the coin."""
        coin = str(question.params["coin"])
        px = self.prices(coin, asof)
        last = sorted(px)[-CONTEXT_DAYS:]
        return {
            "domain": DOMAIN,
            "asof": asof.isoformat(),
            "attribution": ATTRIBUTION,
            "coin": question.params["coin_name"],
            "daily_usd_00utc": [{"day": d.isoformat(), "price": px[d]} for d in last],
        }

    def _p0p1(self, question: Question) -> tuple[float | None, float | None]:
        px = self.prices(str(question.params["coin"]), datetime.max.replace(tzinfo=UTC))
        return (
            px.get(date.fromisoformat(str(question.params["p0_day"]))),
            px.get(date.fromisoformat(str(question.params["p1_day"]))),
        )

    def resolve(self, question: Question, now: datetime) -> Resolution | Void | None:
        """Needs both P0 and P1."""
        if now < question.resolve_after:
            return None
        p0, p1 = self._p0p1(question)
        if p0 is None or p1 is None:
            if now >= question.resolve_after + GRACE:
                return Void(question_id=question.question_id, reason_code="source_missing",
                            detail="P0 or P1 not published by the end of grace",
                            voided_at=now)  # fmt: skip
            return None
        r = logret(p0, p1)
        if question.template == "bigmove":
            assert question.threshold is not None
            value, outcome = abs(r), int(abs(r) > question.threshold)
        else:
            value, outcome = r, int(r > 0)
        coin = str(question.params["coin"])
        url, sha = self.evidence.get(coin, (SOURCE_URL.format(coin=coin), "0" * 64))
        return Resolution(
            question_id=question.question_id,
            outcome=outcome,  # type: ignore[arg-type]
            observed_value=value,
            resolved_at=now,
            evidence=Evidence(source_url=url, snapshot_sha256=sha,
                              values_used={"p0": p0, "p1": p1, "log_return": r}),
        )  # fmt: skip

    def revised(self, question: Question, first: Resolution) -> bool:
        """True if P0 or P1 changed after the first resolution."""
        used = first.evidence.values_used
        return self._p0p1(question) != (used.get("p0"), used.get("p1"))


def crypto_domain_from_prices(
    prices: Mapping[str, Mapping[date, float]],
    evidence: Mapping[str, tuple[str, str]],
    on_skip: Callable[[str], None] | None = None,
) -> CryptoDomain:
    """Build a domain from fetched daily prices."""
    store = AsOfStore()
    add_prices(store, prices)
    return CryptoDomain(store, evidence=evidence, on_skip=on_skip)
