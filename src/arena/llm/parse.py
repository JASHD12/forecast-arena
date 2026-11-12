"""Strict parsing of the forecast answer (SPEC 9.2). Never substitutes a number."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

from arena.models import MAX_RATIONALE_WORDS

KEYS = {"probability", "rationale", "key_factors"}
MAX_FACTORS = 8


class ParseError(Exception):
    """The answer does not match the output contract."""


@dataclass(frozen=True)
class Answer:
    """A parsed answer."""

    probability: float
    rationale: str
    key_factors: tuple[str, ...]


def parse_answer(text: str) -> Answer:
    """Parse exactly one JSON object with exactly the contract's keys.

    Whitespace around the object is allowed; anything else (prose, code fences, extra or
    missing keys, a probability outside [0, 1], a boolean, NaN) is rejected.
    """
    s = text.strip()
    if not (s.startswith("{") and s.endswith("}")):
        raise ParseError("answer is not a bare JSON object")
    try:
        obj = json.loads(s, parse_constant=_no_constants)
    except json.JSONDecodeError as exc:
        raise ParseError(f"invalid JSON: {exc.msg}") from exc
    if not isinstance(obj, dict) or set(obj) != KEYS:
        got = sorted(obj) if isinstance(obj, dict) else type(obj).__name__
        raise ParseError(f"expected keys {sorted(KEYS)}, got {got}")
    p = obj["probability"]
    if isinstance(p, bool) or not isinstance(p, int | float) or not math.isfinite(p):
        raise ParseError("probability must be a number")
    if not 0.0 <= float(p) <= 1.0:
        raise ParseError(f"probability {p} outside [0, 1]")
    r = obj["rationale"]
    if not isinstance(r, str) or not r.strip():
        raise ParseError("rationale must be a non-empty string")
    if len(r.split()) > MAX_RATIONALE_WORDS:
        raise ParseError(f"rationale longer than {MAX_RATIONALE_WORDS} words")
    kf = obj["key_factors"]
    if not isinstance(kf, list) or not all(isinstance(x, str) for x in kf):
        raise ParseError("key_factors must be a list of strings")
    return Answer(float(p), r.strip(), tuple(x.strip() for x in kf[:MAX_FACTORS]))


def _no_constants(name: str) -> float:
    raise ParseError(f"non-finite constant {name}")
