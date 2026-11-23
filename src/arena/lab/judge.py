"""LLM-as-judge for stored rationales, calibrated against human labels (T252b).

A judge model grades a stored live rationale on three 1-5 scales (rubric below). The rubric asks
for the reasoning first and a constrained JSON answer, as in Anthropic's published guidance on
LLM graders. The judge is only trusted as far as it agrees with a human: the owner labels 30 of
the same rationales (HUMAN_TODO H29) and `weighted_kappa` reports the agreement. The judge never
sees which forecaster wrote a rationale.

Items are frozen in `lab/judge/items.json` (built from the public ledger by
`arena lab judge-sheet`), so the paid run needs no ledger access and the judge and the human
grade exactly the same text.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

DIMENSIONS = ("data_use", "direction", "hedging")
CONTEXT_CHARS = 1500
N_ITEMS = 100
N_LABELS = 30
SEED = 20261122

RUBRIC = """You grade the quality of a forecaster's written rationale for a yes/no forecast.
You see the question, its resolution rule, an excerpt of the data the forecaster had, the
forecaster's probability that the answer is YES, and its rationale. Do not guess the outcome.

Score each dimension from 1 (poor) to 5 (excellent):
- data_use: does the rationale use the numbers in the data excerpt correctly (no invented or
  misquoted figures, relevant values chosen)?
- direction: does the stated probability follow from the rationale (a rationale that argues for
  YES should not end with a low probability, and the reverse)?
- hedging: is the confidence appropriate for the evidence (no certainty from thin data, no
  needless vagueness)?

First think step by step in 'reasoning' (at most 40 words), then answer with exactly one JSON
object and nothing else:
{"reasoning": "...", "data_use": 1-5, "direction": 1-5, "hedging": 1-5}"""


class JudgeError(Exception):
    """The judge's answer does not match the output contract."""


def item_id(key: str) -> str:
    """A short opaque id, so a grader cannot read the forecaster from it."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]


def select_items(
    candidates: Sequence[Mapping[str, Any]], n: int = N_ITEMS, seed: int = SEED
) -> list[dict[str, Any]]:
    """A seeded sample of `n` candidates, spread evenly over forecasters (round robin)."""
    by_f: dict[str, list[Mapping[str, Any]]] = {}
    for c in sorted(candidates, key=lambda c: c["key"]):
        by_f.setdefault(c["forecaster_id"], []).append(c)
    rng = random.Random(seed)
    for lst in by_f.values():
        rng.shuffle(lst)
    out: list[Mapping[str, Any]] = []
    while len(out) < n and any(by_f.values()):
        for f in sorted(by_f):
            if by_f[f] and len(out) < n:
                out.append(by_f[f].pop())
    return sorted((dict(c) for c in out), key=lambda c: c["key"])


def label_subset(items: Sequence[Mapping[str, Any]], n: int = N_LABELS) -> list[dict[str, Any]]:
    """The items the owner labels: a seeded subset of the judge's items, in a stable order."""
    rng = random.Random(SEED + 1)
    pick = rng.sample(range(len(items)), min(n, len(items)))
    return [dict(items[i]) for i in sorted(pick)]


def user_prompt(item: Mapping[str, Any]) -> str:
    """What the judge sees for one item (no forecaster name)."""
    return (
        f"Question: {item['question']}\n\nResolution rule: {item['rule']}\n\n"
        f"Data excerpt (JSON, cut off after {CONTEXT_CHARS} characters):\n{item['context']}\n\n"
        f"Forecaster's probability of YES: {item['probability']:.2f}\n\n"
        f"Rationale:\n{item['rationale']}"
    )


def compact_excerpt(text: str, limit: int = CONTEXT_CHARS) -> str:
    """The data excerpt without JSON punctuation, so a person can read it (labelling cards)."""
    flat = re.sub(r'"day":\s*"([^"]+)",\s*"(\w+)":\s*(-?[\d.]+|null)', r"\1 = \3", text)
    flat = re.sub(r'[{}\[\]"]', " ", flat)
    flat = re.sub(r"\s*,\s*", ", ", flat)
    flat = re.sub(r"\s+", " ", flat).strip()
    return flat if len(flat) <= limit else flat[:limit].rstrip() + " ... (cut off)"


def cards_markdown(items: Sequence[Mapping[str, Any]]) -> str:
    """One readable card per item for the owner's labels (HUMAN_TODO H29); no forecaster names."""
    lines = [
        "# Judge labelling cards (30 items)",
        "",
        "Read each card, then rate the rationale on three scales from 1 (poor) to 5 (excellent). "
        "Do not guess the outcome. The data excerpt is the one the judge sees, with JSON "
        "punctuation removed; it can end mid-sentence because it is cut off.",
        "",
        "- **data_use**: are the numbers in the rationale used correctly, none invented or "
        "misquoted?",
        "- **direction**: does the probability follow from the rationale (an argument for YES "
        "should not end with a low probability, and the reverse)?",
        "- **hedging**: is the confidence right for the evidence (no certainty from thin data, no "
        "needless vagueness)?",
        "",
        "Send back 30 lines in the form `id,data_use,direction,hedging`, for example "
        "`9dcceff67a,4,5,3`.",
        "",
    ]
    for n, it in enumerate(items, start=1):
        lines += [
            f"## {n}. `{it['id']}`",
            "",
            f"**Question:** {it['question']}",
            "",
            f"**Resolves YES if:** {it['rule']}",
            "",
            f"**Data the forecaster had:** {compact_excerpt(str(it['context']))}",
            "",
            f"**Probability of YES:** {float(it['probability']):.0%}",
            "",
            f"**Rationale:** {it['rationale']}",
            "",
            f"Your line: `{it['id']},_,_,_`",
            "",
        ]
    return "\n".join(lines)


def parse_judgement(text: str) -> dict[str, Any]:
    """The three scores (ints 1-5) and the reasoning; anything else is rejected, never guessed."""
    s = text.strip()
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if not m:
        raise JudgeError("no JSON object in the judge's answer")
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise JudgeError(f"invalid JSON: {exc}") from exc
    out: dict[str, Any] = {"reasoning": str(obj.get("reasoning", ""))[:600]}
    for d in DIMENSIONS:
        v = obj.get(d)
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
            raise JudgeError(f"{d} must be an integer from 1 to 5, got {v!r}")
        out[d] = v
    return out


def weighted_kappa(a: Sequence[int], b: Sequence[int], categories: int = 5) -> float | None:
    """Quadratic-weighted Cohen's kappa between two raters on 1..categories (None if undefined)."""
    n = len(a)
    if n == 0 or n != len(b):
        return None
    obs = [[0.0] * categories for _ in range(categories)]
    for x, y in zip(a, b, strict=True):
        obs[x - 1][y - 1] += 1
    ra, rb = Counter(a), Counter(b)
    num = den = 0.0
    for i in range(categories):
        for j in range(categories):
            w = ((i - j) / (categories - 1)) ** 2
            exp = ra[i + 1] * rb[j + 1] / n
            num += w * obs[i][j]
            den += w * exp
    if den == 0:
        return None
    return 1 - num / den
