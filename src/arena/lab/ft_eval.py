"""Evaluation of the QLoRA fine-tune on the two frozen test sets (T246).

Inputs are the Colab score files (probabilities already calibrated by a Platt map fitted on the
validation split only), the committed test rows (for the base rate and the batch day), and,
optionally, backtest forecasts of the live `ml` model for the same questions. Every comparison is
paired on identical items and uses a day-block bootstrap interval (`scoring.stats`).
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from arena.scoring import stats

SPLITS = ("test_oct", "test_nov")


def read_scores(paths: Sequence[Path]) -> dict[str, dict[str, dict[str, Any]]]:
    """{variant: {item id: {p, margin, outcome, split}}} from Colab score files."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            out.setdefault(d["variant"], {})[d["id"]] = d
    return out


def read_backtest(run_dir: Path, forecaster: str = "ml") -> dict[str, float]:
    """{question id: probability} of one forecaster from a stored backtest run."""
    out: dict[str, float] = {}
    for line in (run_dir / "forecasts.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["forecaster_id"] == forecaster:
            out[r["question_id"]] = float(r["probability"])
    return out


def log_score(p: Sequence[float], y: Sequence[int]) -> float:
    """Mean negative log likelihood on clipped probabilities (lower is better)."""
    q = np.clip(np.asarray(p, float), 0.01, 0.99)
    t = np.asarray(y, float)
    return float(-np.mean(t * np.log(q) + (1 - t) * np.log(1 - q)))


def arm_metrics(p: Sequence[float], y: Sequence[int]) -> dict[str, float | int]:
    """n, Brier, log score and ECE of one arm on one item set."""
    return {
        "n": len(p),
        "brier": round(float(np.mean(stats.brier_terms(p, y))), 4),
        "log_score": round(log_score(p, y), 4),
        "ece": round(stats.expected_calibration_error(list(p), list(y)), 4),
    }


def evaluate(
    scores: Mapping[str, Mapping[str, Mapping[str, Any]]],
    rows: Mapping[str, Mapping[str, Any]],
    ml: Mapping[str, float] | None = None,
    pairs: Sequence[tuple[str, str]] = (),
) -> tuple[dict[str, dict[str, float | int]], list[dict[str, Any]]]:
    """Metrics per (arm, split) and paired Brier differences on identical items.

    `rows` maps item id to {split, batch_date, base_rate, outcome}. Arms: every Colab variant,
    `base_rate`, and `ml` when backtest probabilities cover the items. `pairs` lists (a, b)
    comparisons; a pair is reported only on items both arms cover."""
    arms: dict[str, dict[str, float]] = {
        v: {i: float(d["p"]) for i, d in s.items()} for v, s in scores.items()
    }
    arms["base_rate"] = {
        i: float(r["base_rate"]) for i, r in rows.items() if r.get("base_rate") is not None
    }
    if ml:
        arms["ml"] = {i: p for i, p in ml.items() if i in rows}
    metrics: dict[str, dict[str, float | int]] = {}
    paired: list[dict[str, Any]] = []
    groups = {**{s: [s] for s in SPLITS}, "test_all": list(SPLITS)}
    for gname, gsplits in groups.items():
        ids_of = {i for i, r in rows.items() if r["split"] in gsplits}
        for arm, probs in arms.items():
            ids = sorted(i for i in ids_of if i in probs)
            if ids:
                metrics[f"{arm} / {gname}"] = arm_metrics(
                    [probs[i] for i in ids], [int(rows[i]["outcome"]) for i in ids]
                )
        for a, b in pairs:
            if a not in arms or b not in arms:
                continue
            ids = sorted(i for i in ids_of if i in arms[a] and i in arms[b])
            if len(ids) < 10:
                continue
            iv = stats.paired_brier_difference(
                [rows[i]["batch_date"] for i in ids],
                [arms[a][i] for i in ids],
                [arms[b][i] for i in ids],
                [int(rows[i]["outcome"]) for i in ids],
            )
            paired.append(
                {
                    "a": a,
                    "b": b,
                    "split": gname,
                    "diff": iv.estimate,
                    "lo": iv.low,
                    "hi": iv.high,
                    "n": iv.n,
                    "days": iv.days,
                }
            )
    return metrics, paired


def finite(x: float) -> bool:
    """True for finite floats."""
    return math.isfinite(x)
