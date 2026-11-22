"""Unsupervised anomaly detection on the daily price rows of a stored context (T294).

An Isolation Forest (Liu, Ting and Zhou, 2008) is fitted on the 27 earlier days of the 28-day
context window (standardised daily mean, maximum, minimum, spread and evening price) and scores the
latest known day: the shorter the path that isolates it, the more anomalous it is. No labels are
needed. The decision thresholds were fixed on clean real windows of the training years in the lab
study (`arena lab anomaly`, false-alarm rate about 5%); the study also reports what each detector
catches when faults are injected (spikes, unit error, flat feed, repeated day). The plain
robust z-score catches more of them than the Isolation Forest on 28-day windows, so both are shown.

Informational, like the data contracts (`ops/contracts.py`): shown on Status, never fails a run or a
clean day (SPEC 2.9 is owner-only).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest

STATS = ("mean", "max", "min", "spread", "evening")
MIN_ROWS = 20
#: Thresholds set on clean real windows of 2019-2024 for about 5% false alarms (lab study).
THRESHOLD = 0.656  # Isolation Forest score
THRESHOLD_Z = 5.85  # robust z-score
N_TREES = 200


def _matrix(rows: Sequence[dict[str, Any]]) -> np.ndarray:
    return np.array([[float(r[s]) for s in STATS] for r in rows], float)


def isolation_score(rows: Sequence[dict[str, Any]], seed: int = 0) -> float:
    """Anomaly score of the last row against the earlier rows (about 0.5 typical, towards 1.0 odd).

    Uses the usual Isolation Forest normalisation `2 ** (-E[h(x)] / c(n))`, recovered from
    scikit-learn's `score_samples` (which returns the negative of it)."""
    if len(rows) < MIN_ROWS:
        raise ValueError(f"only {len(rows)} daily rows (need {MIN_ROWS})")
    x = _matrix(rows)
    train, last = x[:-1], x[-1:]
    mu, sd = train.mean(axis=0), train.std(axis=0)
    sd[sd == 0] = 1.0
    forest = IsolationForest(n_estimators=N_TREES, random_state=seed, contamination="auto")
    forest.fit((train - mu) / sd)
    return float(-forest.score_samples((last - mu) / sd)[0])


def robust_z(rows: Sequence[dict[str, Any]]) -> float:
    """Baseline: the largest |z| of the last row's statistics using median and MAD of the rest."""
    x = _matrix(rows)
    train, last = x[:-1], x[-1]
    med = np.median(train, axis=0)
    mad = np.median(np.abs(train - med), axis=0) * 1.4826
    mad[mad == 0] = 1.0
    return float(np.max(np.abs(last - med) / mad))


def check_rows(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Score and flag of a context's daily rows (power); fewer rows raise `ValueError`."""
    score, z = isolation_score(rows), robust_z(rows)
    return {
        "day": rows[-1].get("day"),
        "isolation_score": round(score, 3),
        "isolation_flag": score > THRESHOLD,
        "robust_z": round(z, 2),
        "robust_z_flag": z > THRESHOLD_Z,
    }


def latest_batch_anomaly(ledger: Any, rec: Any, day: Any) -> dict[str, Any] | None:
    """Anomaly check of the power context stored for a batch day (None: nothing to check)."""
    import gzip
    import json

    from arena.ledger import layout

    qs = sorted(
        (q for q in rec.questions.values() if q.batch_date == day and q.domain == "power"),
        key=lambda q: q.question_id,
    )
    rel = f"{layout.snapshot_dir('power', day)}/morning_context.json.gz"
    if not qs or not ledger.exists(rel):
        return None
    ctx = json.loads(gzip.decompress(ledger.read_bytes(rel))).get(qs[0].question_id)
    try:
        return check_rows(ctx["daily"]) if ctx else None
    except (KeyError, ValueError, TypeError):
        return None
