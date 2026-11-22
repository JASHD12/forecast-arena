"""Distillation labels from a teacher model (T247, `lab/prereg/distill.md`).

The teacher (Claude Haiku, the live forecaster model) gives a probability for a seeded, balanced
sample of **training-split** questions only. A small open student is then trained on those soft
labels instead of the hard outcomes; the comparison is cost per 1,000 questions against quality.
This module holds the deterministic parts (the sample and the label file format); the paid run is
`arena lab distill-labels`.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Sequence
from pathlib import Path

from arena.lab.dataset import Row

SEED = 20261123


def sample_rows(train: Sequence[Row], n: int, seed: int = SEED) -> list[Row]:
    """`n` training rows spread over the question templates (round robin), seeded, sorted by id."""
    rng = random.Random(seed)
    by_t: dict[str, list[Row]] = {}
    for r in sorted(train, key=lambda r: r.id):
        by_t.setdefault(r.template, []).append(r)
    for rows in by_t.values():
        rng.shuffle(rows)
    out: list[Row] = []
    while len(out) < n and any(by_t.values()):
        for t in sorted(by_t):
            if by_t[t] and len(out) < n:
                out.append(by_t[t].pop())
    return sorted(out, key=lambda r: r.id)


def labels_file(
    ids: Sequence[str], probs: Sequence[float | None], summary: dict[str, object]
) -> dict[str, object]:
    """The committed label file: ids, teacher probabilities (null = skipped) and the run summary."""
    if len(ids) != len(probs):
        raise ValueError("ids and probabilities differ in length")
    return {
        "teacher": summary.get("model"),
        "ids": list(ids),
        "p": list(probs),
        "ids_sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
        "summary": summary,
    }


def write_labels(path: Path, data: dict[str, object]) -> None:
    """Write the label file as stable JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")


def usable(
    ids: Sequence[str], probs: Sequence[float | None], train: Sequence[Row]
) -> list[tuple[str, float]]:
    """Labelled ids that are training rows (a label for a validation or test row is an error)."""
    train_ids = {r.id for r in train}
    out = []
    for i, p in zip(ids, probs, strict=True):
        if p is None:
            continue
        if i not in train_ids:
            raise ValueError(f"{i} is not a training row (leakage)")
        out.append((i, float(p)))
    return out
