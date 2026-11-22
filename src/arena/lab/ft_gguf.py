"""Scoring the validation and test sets with the deployed GGUF, and calibrating on those margins.

The Colab run fitted the Platt map on the margins of the 4-bit training model; the GGUF is a
different numerical object (merged, quantised, run by llama.cpp), and its parity check missed the
pre-registered limit. Scoring every validation and test row with the GGUF itself and refitting the
map on the validation margins only (rule L3) calibrates the artefact that would actually run live.
The work is split into shards so that parallel runners finish within the job time limit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SPLITS = ("val", "test_oct", "test_nov")


def shard(items: Sequence[Any], index: int, count: int) -> list[Any]:
    """Every `count`-th item starting at `index` (round robin, so shards are balanced)."""
    if not 0 <= index < count:
        raise ValueError(f"shard {index} of {count}")
    return [x for i, x in enumerate(items) if i % count == index]


def merge(parts: Sequence[Mapping[str, float]]) -> dict[str, float]:
    """Union of shard results; the same id twice is an error (shards must not overlap)."""
    out: dict[str, float] = {}
    for part in parts:
        for k, v in part.items():
            if k in out:
                raise ValueError(f"item {k} scored twice")
            out[k] = float(v)
    return out


def calibrate(
    margins: Mapping[str, float],
    rows: Mapping[str, Mapping[str, Any]],
    old_platt: tuple[float, float],
) -> dict[str, Any]:
    """Refit Platt on validation margins only; Brier of the old and the new map per split.

    `rows` maps id to {split, outcome}. Every row of the three splits must have a margin."""
    # imported here: the scoring runners have no PyTorch, only the calibration step needs it
    from arena.lab.finetune import train as tr

    missing = [i for i, r in rows.items() if r["split"] in SPLITS and i not in margins]
    if missing:
        raise ValueError(f"{len(missing)} rows have no margin, e.g. {missing[0]}")
    val = [i for i, r in rows.items() if r["split"] == "val"]
    a, b = tr.fit_platt([margins[i] for i in val], [int(rows[i]["outcome"]) for i in val])
    out: dict[str, Any] = {"platt_new": [a, b], "platt_old": list(old_platt), "splits": {}}
    for split in SPLITS:
        ids = [i for i, r in rows.items() if r["split"] == split]
        y = [int(rows[i]["outcome"]) for i in ids]
        out["splits"][split] = {
            "n": len(ids),
            "brier_old_platt": round(
                tr.brier([tr.apply_platt(margins[i], *old_platt) for i in ids], y), 4
            ),
            "brier_new_platt": round(
                tr.brier([tr.apply_platt(margins[i], a, b) for i in ids], y), 4
            ),
        }
    return out
