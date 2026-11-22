"""Offline prompt optimisation for the free local model (T297, `lab/prereg/prompt-opt.md`).

Candidates are an instruction variant and a number of solved examples (shots). They are scored
with the single-token margin of the local GGUF on a validation subsample; the winner by
cross-fitted Brier and the baseline are then scored once on the frozen test sets. Everything here
is deterministic and runs on CPU; the scorer is injected so tests use a fake.
"""

from __future__ import annotations

import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from arena.lab.dataset import Row

N_SEARCH_ROWS = 48
SEED = 20261122
SHOTS = 4

#: Extra lines appended to the live system prompt; index 0 leaves it unchanged.
INSTRUCTIONS: tuple[str, ...] = (
    "",
    "Answer with exactly one word: YES or NO.",
    "Start from the base rate and move away from it only when the recent daily values clearly "
    "cross the threshold. Answer with exactly one word: YES or NO.",
    "First compare the threshold with the last seven daily values in the data, then answer with "
    "exactly one word: YES or NO.",
)


@dataclass(frozen=True)
class Candidate:
    """One prompt variant: an instruction index and a number of shots."""

    instruction: int
    shots: int

    @property
    def id(self) -> str:
        """Stable short name, e.g. `i2s4`."""
        return f"i{self.instruction}s{self.shots}"


BASELINE = Candidate(0, 0)


def candidates() -> list[Candidate]:
    """The eight pre-registered candidates, baseline first."""
    return [Candidate(i, s) for s in (0, SHOTS) for i in range(len(INSTRUCTIONS))]


def question_of(row: Row) -> str:
    """The question sentence of a row's user prompt."""
    m = re.search(r"^Question: (.*)$", row.user, re.MULTILINE)
    return m.group(1).strip() if m else row.user.splitlines()[0]


def pick_shots(train: Sequence[Row], k: int, seed: int = SEED) -> list[Row]:
    """k train rows, balanced YES and NO, seeded; empty for k = 0."""
    if k <= 0:
        return []
    rng = random.Random(seed)
    yes = [r for r in train if r.outcome == 1]
    no = [r for r in train if r.outcome == 0]
    rng.shuffle(yes)
    rng.shuffle(no)
    half = k // 2
    chosen = yes[:half] + no[: k - half]
    rng.shuffle(chosen)
    return chosen


def render(row: Row, cand: Candidate, shots: Sequence[Row]) -> tuple[str, str]:
    """(system, user) for one row under a candidate; the user text is never changed."""
    system = row.system
    if INSTRUCTIONS[cand.instruction]:
        system = f"{system.rstrip()}\n\n{INSTRUCTIONS[cand.instruction]}"
    if cand.shots and shots:
        lines = [
            f"- {question_of(s)} -> {'YES' if s.outcome else 'NO'}" for s in shots[: cand.shots]
        ]
        system += "\n\nSolved examples of similar questions from the past:\n" + "\n".join(lines)
    return system, row.user


def search_rows(val: Sequence[Row], n: int = N_SEARCH_ROWS, seed: int = SEED) -> list[Row]:
    """A seeded validation subsample, spread over the question templates, sorted by id."""
    rng = random.Random(seed)
    by_template: dict[str, list[Row]] = {}
    for r in sorted(val, key=lambda r: r.id):
        by_template.setdefault(r.template, []).append(r)
    for rows in by_template.values():
        rng.shuffle(rows)
    picked: list[Row] = []
    while len(picked) < n and any(by_template.values()):
        for t in sorted(by_template):
            if by_template[t] and len(picked) < n:
                picked.append(by_template[t].pop())
    return sorted(picked, key=lambda r: r.id)


def fit_platt(margins: Sequence[float], outcomes: Sequence[int]) -> tuple[float, float]:
    """Platt map (a, b) by logistic regression on the margin; (0, base rate logit) if one class."""
    y = np.asarray(outcomes, int)
    if y.min() == y.max():
        p = (y.sum() + 1) / (len(y) + 2)
        return 0.0, float(np.log(p / (1 - p)))
    from sklearn.linear_model import LogisticRegression

    lr = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
    lr.fit(np.asarray(margins, float).reshape(-1, 1), y)
    return float(lr.coef_[0][0]), float(lr.intercept_[0])


def apply_platt(margin: float, platt: tuple[float, float]) -> float:
    """Calibrated probability clipped to [0.01, 0.99] like the scoring code."""
    z = platt[0] * margin + platt[1]
    p = 1 / (1 + np.exp(-z))
    return float(min(0.99, max(0.01, p)))


def brier(p: Sequence[float], y: Sequence[int]) -> float:
    """Mean squared error of probabilities."""
    return float(np.mean([(a - b) ** 2 for a, b in zip(p, y, strict=True)]))


def cross_fitted_brier(margins: Sequence[float], outcomes: Sequence[int]) -> float:
    """Brier with the Platt map fitted on one half and scored on the other (both ways)."""
    n = len(margins)
    idx = list(range(n))
    folds = [idx[0::2], idx[1::2]]
    preds: dict[int, float] = {}
    for held, fit in ((folds[0], folds[1]), (folds[1], folds[0])):
        platt = fit_platt([margins[i] for i in fit], [outcomes[i] for i in fit])
        for i in held:
            preds[i] = apply_platt(margins[i], platt)
    return brier([preds[i] for i in idx], list(outcomes))


def choose(scores: Mapping[str, float]) -> str:
    """Candidate id with the lowest score; ties and anything not strictly better go to baseline."""
    best = min(scores, key=lambda k: (scores[k], k != BASELINE.id, k))
    if scores[best] < scores[BASELINE.id]:
        return best
    return BASELINE.id


def score_candidate(
    scorer: Any,
    cand: Candidate,
    rows: Sequence[Row],
    train: Sequence[Row],
) -> list[float]:
    """Margins of every row under a candidate, in row order."""
    shots = pick_shots(train, cand.shots)
    return [scorer.margin(*render(r, cand, shots)) for r in rows]
