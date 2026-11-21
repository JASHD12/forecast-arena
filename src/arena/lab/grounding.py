"""Numeric grounding of model rationales (T252a): is every number traceable to the prompt?

A non-trivial number quoted in a rationale is `grounded` if it equals (within its own rounding,
or 1%) a number in the question, the resolution rule or the as-of context the forecaster was
given, and `not_in_prompt` otherwise. Not in the prompt is an upper bound on invented figures:
a model may legitimately compute a mean or a difference. An earlier draft tried to classify
such arithmetic as "derived", but with hundreds of context numbers almost any value is a
difference of two of them by chance, so the class was dropped; the LLM judge (T252b) is the
tool for judging calculations.

Trivial numbers (integers below 10, years and ISO dates) are ignored: they count days or items.
"""

from __future__ import annotations

import gzip
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> list[tuple[float, int]]:
    """Numbers of a text as (value, decimals); thousands commas removed; dates dropped."""
    text = _ISO_DATE.sub(" ", text)
    out = []
    for m in _NUMBER.finditer(text):
        raw = m.group(0).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        out.append((value, len(raw.split(".")[1]) if "." in raw else 0))
    return out


def is_trivial(value: float, decimals: int) -> bool:
    """Small integers and calendar years carry no data."""
    return decimals == 0 and (abs(value) < 10 or 1990 <= abs(value) <= 2100)


def context_numbers(obj: Any) -> list[float]:
    """Every numeric leaf of a JSON-like context, plus the numbers inside its strings."""
    out: list[float] = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, int | float):
        out.append(float(obj))
    elif isinstance(obj, str):
        out.extend(v for v, _ in numbers_in(obj))
    elif isinstance(obj, Mapping):
        for v in obj.values():
            out.extend(context_numbers(v))
    elif isinstance(obj, Sequence):
        for v in obj:
            out.extend(context_numbers(v))
    return out


def _close(x: float, y: float, decimals: int) -> bool:
    tol = max(0.5 * 10 ** (-decimals), 0.01 * abs(y)) if decimals >= 0 else 0.01 * abs(y)
    return abs(x - y) <= tol + 1e-9


def classify(value: float, decimals: int, refs: Sequence[float]) -> str:
    """`grounded` or `not_in_prompt` for one rationale number."""
    return "grounded" if any(_close(value, r, decimals) for r in refs) else "not_in_prompt"


def check(rationale: str, reference_texts: Iterable[str], context: Any = None) -> dict[str, int]:
    """Counts of grounded and not-in-prompt non-trivial numbers of one rationale."""
    refs = [v for t in reference_texts for v, _ in numbers_in(t)] + context_numbers(context)
    counts = {"grounded": 0, "not_in_prompt": 0}
    for value, decimals in numbers_in(rationale):
        if is_trivial(value, decimals):
            continue
        counts[classify(value, decimals, refs)] += 1
    return counts


def summarize(per_item: Sequence[Mapping[str, int]]) -> dict[str, float | int]:
    """Metrics of one forecaster: rationales, numbers and the share not found in the prompt."""
    numbers = sum(sum(c.values()) for c in per_item)
    missing = sum(c["not_in_prompt"] for c in per_item)
    return {
        "n": len(per_item),
        "numbers": numbers,
        "not_in_prompt_pct": round(100 * missing / numbers, 1) if numbers else 0.0,
        "rationales_with_not_in_prompt_pct": round(
            100 * sum(1 for c in per_item if c["not_in_prompt"]) / len(per_item), 1
        )
        if per_item
        else 0.0,
    }


def rationale_checks(
    ledger: Any, rec: Any, first_day: date | None = None
) -> dict[str, list[dict[str, int]]]:
    """Per forecaster: the grounding counts of every stored rationale (and key factors) whose
    morning context snapshot exists, optionally only for batch days from `first_day`."""
    from arena.ledger import layout

    snaps: dict[tuple[str, date], dict[str, Any]] = {}
    per: dict[str, list[dict[str, int]]] = {}
    for f in rec.forecasts:
        q = rec.questions.get(f.question_id)
        if q is None or not f.rationale or (first_day is not None and q.batch_date < first_day):
            continue
        key = (q.domain, q.batch_date)
        if key not in snaps:
            rel = f"{layout.snapshot_dir(q.domain, q.batch_date)}/morning_context.json.gz"
            snaps[key] = (
                json.loads(gzip.decompress(ledger.read_bytes(rel))) if ledger.exists(rel) else {}
            )
        ctx = snaps[key].get(q.question_id)
        if ctx is None:  # no stored context for this question: nothing to compare with
            continue
        text = f.rationale + " " + " ".join(map(str, f.meta.get("key_factors") or []))
        per.setdefault(f.forecaster_id, []).append(check(text, [q.text, q.resolution_rule], ctx))
    return per
