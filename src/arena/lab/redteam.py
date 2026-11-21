"""Red-team harness for the guards (T253): detection per attack category and false positives."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from arena.llm.guards import sanitize


def load_cases(path: Path) -> list[dict[str, Any]]:
    """The case list of `lab/redteam/cases.json`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data["cases"])


def flagged(text: str) -> bool:
    """True if the guard found anything in `text` (pattern, markup, link, code or length)."""
    return bool(sanitize(text).flags)


def injected(text: str) -> bool:
    """True if the guard replaced the text because it looked like an instruction."""
    return sanitize(text).text.startswith("[removed: instruction-like text]")


def run(cases: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, float | int]]:
    """Per category: cases, detections and the rate; false positives for the benign texts."""
    by_cat: dict[str, list[bool]] = defaultdict(list)
    for c in cases:
        by_cat[c["category"]].append(flagged(c["text"]))
    out: dict[str, dict[str, float | int]] = {}
    attacks = [d for cat, ds in by_cat.items() if cat != "benign" for d in ds]
    for cat, ds in sorted(by_cat.items()):
        if cat == "benign":
            out[cat] = {
                "n": len(ds),
                "flagged": sum(ds),
                "false_positive_pct": round(100 * sum(ds) / len(ds), 1),
            }
        else:
            out[cat] = {
                "n": len(ds),
                "flagged": sum(ds),
                "detected_pct": round(100 * sum(ds) / len(ds), 1),
            }
    out["all_attacks"] = {
        "n": len(attacks),
        "flagged": sum(attacks),
        "detected_pct": round(100 * sum(attacks) / len(attacks), 1) if attacks else 0.0,
    }
    return out
