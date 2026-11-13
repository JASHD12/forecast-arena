"""LLM observability (T123): spans from `agent_traces/`, usage, latency and estimated cost.

Cost is an *estimate*: tokens recorded in the spans times a dated list price. It is not an
invoice. Output tokens include thinking tokens (the provider bills them as output). The
local model (`llama_cpp`) costs nothing per call.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

from arena.ledger import Ledger, layout

#: model id prefix -> (input USD per 1M tokens, output USD per 1M tokens), for prompts up
#: to 100K tokens (ours are far smaller). Source and date are shown with every figure.
PRICES: dict[str, tuple[float, float]] = {"claude-haiku-5-5": (0.10, 0.50)}
PRICE_SOURCE = "Anthropic list prices for Claude Haiku 5.5 as of 2026-11-03 (docs/SOURCES.md)"
FREE_PROVIDERS = frozenset({"llama_cpp"})


def price_for(provider: str, model: str) -> tuple[float, float] | None:
    """(input, output) USD per 1M tokens, (0, 0) for local models, None if unknown."""
    if provider in FREE_PROVIDERS:
        return (0.0, 0.0)
    for prefix, p in PRICES.items():
        if model.startswith(prefix):
            return p
    return None


def load_spans(ledger: Ledger) -> list[dict[str, Any]]:
    """Every span in the ledger, with its batch day added."""
    out: list[dict[str, Any]] = []
    for rel in ledger.list_files("agent_traces"):
        day = layout.day_of(rel)
        for line in ledger.read_bytes(rel).decode("utf-8").splitlines():
            if not line.strip():
                continue
            for s in json.loads(line).get("spans", []):
                out.append({**s, "day": day})
    return out


def traces_by_question(ledger: Ledger) -> dict[str, list[dict[str, Any]]]:
    """Trace lines (tool calls, outcome, spans) per question id, sorted by forecaster."""
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rel in ledger.list_files("agent_traces"):
        for line in ledger.read_bytes(rel).decode("utf-8").splitlines():
            if line.strip():
                t = json.loads(line)
                out[str(t.get("question_id", ""))].append(t)
    return {k: sorted(v, key=lambda t: str(t.get("forecaster_id"))) for k, v in out.items()}


def _pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, max(0, math.ceil(q * len(s)) - 1))]


@dataclass(frozen=True)
class UsageRow:
    """Calls of one forecaster on one day."""

    day: date | None
    forecaster_id: str
    model: str
    calls: int
    errors: int
    repairs: int
    input_tokens: int
    output_tokens: int
    p50_ms: float | None
    p95_ms: float | None
    cost_usd: float | None


def usage_rows(spans: list[dict[str, Any]]) -> list[UsageRow]:
    """One row per (day, forecaster, model), newest day first."""
    groups: dict[tuple[Any, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for s in spans:
        key = (s.get("day"), s["forecaster_id"], s.get("provider", ""), s.get("model", ""))
        groups[key].append(s)
    rows = []
    for (day, fid, provider, model), ss in groups.items():
        inp = sum(int(s.get("input_tokens", 0)) for s in ss)
        outp = sum(int(s.get("output_tokens", 0)) for s in ss)
        price = price_for(provider, model)
        cost = None if price is None else (inp * price[0] + outp * price[1]) / 1e6
        ms = [float(s["duration_ms"]) for s in ss if s.get("error") is None]
        rows.append(
            UsageRow(
                day,
                fid,
                model,
                len(ss),
                sum(1 for s in ss if s.get("error")),
                sum(1 for s in ss if s.get("repair")),
                inp,
                outp,
                _pct(ms, 0.5),
                _pct(ms, 0.95),
                cost,
            )
        )
    return sorted(rows, key=lambda r: (str(r.day), r.forecaster_id), reverse=True)


def totals(rows: list[UsageRow]) -> dict[str, Any]:
    """Totals over all rows (cost only over rows with a known price)."""
    known = [r.cost_usd for r in rows if r.cost_usd is not None]
    return {
        "calls": sum(r.calls for r in rows),
        "input_tokens": sum(r.input_tokens for r in rows),
        "output_tokens": sum(r.output_tokens for r in rows),
        "cost_usd": sum(known) if known else None,
        "unpriced": sum(1 for r in rows if r.cost_usd is None),
    }
