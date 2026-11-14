"""Run prompt variants over the golden set and compute evaluation metrics (T124).

Variants are the LLM forecasters with their versioned prompts (`llm_plain` and
`llm_context`, plus `llm_local` when the local model is available): the same model, A/B
over the information and prompt each one gets. Every call goes through a `BudgetGuard`
with the eval's own caps and a `TracingLLM`, so tokens, repairs and errors are measured
from the same spans as in the live system.

Metrics per variant: answered share, Brier and log score, expected calibration error,
skill against the golden `base_rate`, JSON validity (first answer usable without a
repair), repair rate, skips by reason, tokens and estimated cost; plus paired Brier
differences between variants with a day-block interval.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from arena.clock import Clock
from arena.evals.golden import GoldenItem
from arena.forecasters.llm import LLMContext, LLMForecaster, LLMLocal, LLMPlain
from arena.llm.budget import BudgetGuard, Caps, GuardedLLM
from arena.llm.client import LLMClient, Usage
from arena.llm.tracing import Tracer, TracingLLM, scope
from arena.models import Forecast
from arena.scoring.core import brier, brier_skill, log_score
from arena.scoring.stats import expected_calibration_error, paired_brier_difference
from arena.site.llm_obs import CACHE_READ_MULT, CACHE_WRITE_MULT, price_for

KIND = "evaluation"
VARIANTS: dict[str, type[LLMForecaster]] = {
    "llm_plain": LLMPlain,
    "llm_context": LLMContext,
    "llm_local": LLMLocal,
}


@dataclass(frozen=True)
class EvalCaps:
    """Hard caps for one eval run (separate from the live daily caps)."""

    max_requests: int = 80
    max_tokens: int = 60_000
    max_output_tokens: int = 400


def _valid_first_try(mine: list[dict[str, Any]], repaired: set[str]) -> float | None:
    """Share of answers that parsed on the first attempt, over the calls that produced an
    answer at all. Provider errors and budget stops say nothing about JSON validity, so
    they are left out (a run where every call failed shows None, not 100%)."""
    answered = [r for r in mine if r["skip"] not in ("error", "budget_exhausted")]
    if not answered:
        return None
    ok = [r for r in answered if r["question_id"] not in repaired and r["skip"] != "parse_failure"]
    return len(ok) / len(answered)


def sample(items: Sequence[GoldenItem], limit: int | None, seed: int = 0) -> list[GoldenItem]:
    """A seeded sample stratified by template, or every item when `limit` is None."""
    if limit is None or limit >= len(items):
        return list(items)
    by_t: dict[str, list[GoldenItem]] = {}
    for it in sorted(items, key=lambda i: i.question.question_id):
        by_t.setdefault(it.question.template, []).append(it)
    rng = random.Random(seed)
    for lst in by_t.values():
        rng.shuffle(lst)
    out: list[GoldenItem] = []
    while len(out) < limit:
        for t in sorted(by_t):
            if by_t[t] and len(out) < limit:
                out.append(by_t[t].pop())
    return sorted(out, key=lambda i: i.question.question_id)


def run(
    items: Sequence[GoldenItem],
    clients: Mapping[str, LLMClient],
    clock: Clock,
    *,
    golden: str,
    golden_sha256: str,
    caps: EvalCaps | None = None,
    now_id: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Evaluate every variant in `clients` on `items`; returns the JSON-ready result."""
    caps = caps or EvalCaps()
    guard = BudgetGuard(
        Caps(caps.max_requests, caps.max_tokens, caps.max_output_tokens, 0), Usage()
    )
    tracer = Tracer()
    rows: list[dict[str, Any]] = []
    versions: dict[str, str] = {}
    for name, client in clients.items():
        f = VARIANTS[name](TracingLLM(GuardedLLM(client, guard), tracer, clock))
        f.max_output_tokens = caps.max_output_tokens
        versions[name] = f.version()
        for it in items:
            with scope(name, it.question.question_id, f.prompt_version):
                r = f.forecast(it.question, it.context, it.asof)
            rows.append(
                {
                    "variant": name,
                    "question_id": it.question.question_id,
                    "day": it.question.batch_date.isoformat(),
                    "outcome": it.outcome,
                    "probability": r.probability if isinstance(r, Forecast) else None,
                    "skip": None if isinstance(r, Forecast) else r.reason_code,
                    # why a call failed (provider error text), so a result file names its cause
                    "detail": None if isinstance(r, Forecast) else str(r.detail)[:300],
                }
            )
    started = clock.now()
    return {
        "kind": KIND,
        "run_id": now_id() if now_id else f"eval-{started:%Y%m%dT%H%M%S}",
        "created_at": started.isoformat(),
        "golden": golden,
        "golden_sha256": golden_sha256,
        "n_items": len(items),
        "caps": {"max_requests": caps.max_requests, "max_tokens": caps.max_tokens},
        "versions": versions,
        "metrics": metrics(rows, items, tracer),
        "paired": paired(rows, list(clients)),
        "rows": rows,
    }


def metrics(
    rows: Sequence[dict[str, Any]], items: Sequence[GoldenItem], tracer: Tracer
) -> dict[str, dict[str, Any]]:
    """Per variant (and the golden base rate as a reference)."""
    base = {it.question.question_id: it.base_rate for it in items}
    out: dict[str, dict[str, Any]] = {}
    for name in sorted({r["variant"] for r in rows}):
        mine = [r for r in rows if r["variant"] == name]
        ok = [r for r in mine if r["probability"] is not None]
        ps, ys = [r["probability"] for r in ok], [r["outcome"] for r in ok]
        spans = [s for s in tracer.spans if s.forecaster_id == name]
        repaired = {s.question_id for s in spans if s.repair}
        ref: list[tuple[dict[str, Any], float]] = []
        for r in ok:
            br = base.get(r["question_id"])
            if br is not None:
                ref.append((r, br))
        b = brier(ps, ys) if ok else None
        b0 = brier([x for _, x in ref], [r["outcome"] for r, _ in ref]) if ref else None
        inp = sum(s.input_tokens for s in spans)
        outp = sum(s.output_tokens for s in spans)
        cr = sum(s.cache_read_tokens for s in spans)
        cw = sum(s.cache_write_tokens for s in spans)
        price = price_for(spans[0].provider, spans[0].model) if spans else None
        billed_in = inp + CACHE_READ_MULT * cr + CACHE_WRITE_MULT * cw
        out[name] = {
            "n": len(mine),
            "answered": len(ok),
            "brier": b,
            "log_score": log_score(ps, ys) if ok else None,
            "ece": expected_calibration_error(ps, ys) if len(ok) >= 10 else None,
            "base_rate_brier_same_items": b0,
            "skill_vs_base_rate": brier_skill(b, b0) if b is not None and b0 else None,
            "json_valid_first_try": _valid_first_try(mine, repaired),
            "repair_rate": len(repaired) / len(mine) if mine else None,
            "skips": dict(Counter(r["skip"] for r in mine if r["skip"])),
            "calls": len(spans),
            "stop_reasons": dict(
                Counter(s.stop_reason or ("error" if s.error else "") for s in spans)
            ),
            "input_tokens": inp,
            "output_tokens": outp,
            "cache_read_tokens": cr,
            "cache_write_tokens": cw,
            "cost_usd": None if price is None else (billed_in * price[0] + outp * price[1]) / 1e6,
            "model": spans[0].model if spans else None,
        }
    return out


def paired(rows: Sequence[dict[str, Any]], names: Sequence[str]) -> list[dict[str, Any]]:
    """Brier(a) - Brier(b) on the questions both answered, with a day-block interval."""
    by = {(r["variant"], r["question_id"]): r for r in rows if r["probability"] is not None}
    out = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            qids = sorted({q for v, q in by if v == a} & {q for v, q in by if v == b})
            if len(qids) < 2:
                continue
            iv = paired_brier_difference(
                [by[(a, q)]["day"] for q in qids],
                [by[(a, q)]["probability"] for q in qids],
                [by[(b, q)]["probability"] for q in qids],
                [by[(a, q)]["outcome"] for q in qids],
            )
            out.append(
                {
                    "a": a,
                    "b": b,
                    "n": len(qids),
                    "diff": iv.estimate,
                    "lo": iv.low,
                    "hi": iv.high,
                    "days": iv.days,
                }
            )
    return out
