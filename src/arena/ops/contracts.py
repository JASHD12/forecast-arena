"""Data contracts for the stored morning contexts (T276): freshness, ranges and completeness.

The source parsers already reject malformed responses (they raise), so these expectations cover what
a parser cannot know: whether the data is *fresh*, *complete* and *plausible* for a question's batch
day. They are informational: a violation is recorded and shown on the Status page and in the health
report, but never fails a run or a clean day (the clean-day rule is SPEC 2.9, owner-only).
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from arena.ledger import Ledger, layout

POWER_PRICE_RANGE = (-500.0, 4000.0)  # EUR/MWh: the harmonised day-ahead price limits
TEMP_RANGE = (-45.0, 55.0)  # degrees C


def _num(x: Any) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool) and x == x  # not NaN


def check_context(domain: str, ctx: Mapping[str, Any], batch_date: date) -> list[str]:
    """Violated expectations of one stored context (empty list: all met)."""
    bad: list[str] = []
    if ctx.get("domain") != domain:
        bad.append(f"domain field is {ctx.get('domain')!r}, expected {domain!r}")
    if not ctx.get("asof"):
        bad.append("no asof time")
    if domain == "power":
        if len(ctx.get("daily") or []) < 28:
            bad.append(f"{len(ctx.get('daily') or [])} daily rows, expected 28")
        hourly = ctx.get("latest_hourly") or []
        if len(hourly) not in (23, 24, 25):
            bad.append(f"{len(hourly)} hourly prices for the latest day, expected 23 to 25")
        lo, hi = POWER_PRICE_RANGE
        if any(not _num(p) or not lo <= p <= hi for p in hourly):
            bad.append("an hourly price is outside the plausible range")
        try:
            if date.fromisoformat(str(ctx.get("latest_day"))) < batch_date - timedelta(days=2):
                bad.append(f"latest price day {ctx.get('latest_day')} is stale")
        except ValueError:
            bad.append("latest_day is missing or not a date")
    elif domain == "weather":
        # a two-city question holds one block per city, a single-city question one block
        blocks = [ctx[k] for k in ("city_a", "city_b") if k in ctx] or [ctx]
        lo, hi = TEMP_RANGE
        for blk in blocks:
            fd = blk.get("forecast_daily") or {}
            if fd and not (_num(fd.get("tmax")) and lo <= fd["tmax"] <= hi):
                bad.append("forecast tmax is missing or implausible")
            if len(blk.get("observed_daily") or []) < 10:
                bad.append("fewer than 10 observed days")
    elif domain == "attention":
        views = ctx.get("daily_views") or []
        if len(views) < 7:
            bad.append(f"{len(views)} days of page views, expected at least 7")
    elif domain == "markets":
        fixings = ctx.get("fixings") or []
        if len(fixings) < 30:
            bad.append(f"{len(fixings)} fixings, expected at least 30")
    return bad


def check_batch(ledger: Ledger, rec: Any, day: date) -> tuple[int, list[str]]:
    """(contexts checked, violations as "domain question: problem") for one batch day."""
    snaps: dict[str, dict[str, Any]] = {}
    checked, out = 0, []
    for q in sorted(rec.questions.values(), key=lambda q: q.question_id):
        if q.batch_date != day:
            continue
        if q.domain not in snaps:
            rel = f"{layout.snapshot_dir(q.domain, day)}/morning_context.json.gz"
            snaps[q.domain] = (
                json.loads(gzip.decompress(ledger.read_bytes(rel))) if ledger.exists(rel) else {}
            )
        ctx = snaps[q.domain].get(q.question_id)
        if ctx is None:
            out.append(f"{q.domain} {q.question_id}: no stored context")
            continue
        checked += 1
        out += [f"{q.domain} {q.question_id}: {p}" for p in check_context(q.domain, ctx, day)]
    return checked, out
