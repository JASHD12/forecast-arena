"""`ml` for attention (SPEC 8.3): boosted classifier on the article's recent trajectory.

Inputs are the same in training and live forecasting: the context's `top_trajectory` (the
article's views and rank on the last 7 published days, from the daily top lists; where it
is absent, the list's lowest count bounds it), the question's K, the project and the
weekday of D. Training rows come from cached top lists only: for each reference day R and
each eligible article ranked 5-200, the label is whether its views on R+3 reach K, read
from the top list of R+3. When the article is missing from that list and K is at or below
the list's lowest count, the label is unknown and the row is dropped.

Calibration: logistic (Platt) map fitted on out-of-fold predictions (expanding window,
never shuffled).
"""

from __future__ import annotations

import hashlib
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from arena.domains.attention import (
    HORIZON,
    LOW_RANK,
    PROJECTS,
    TOP_RANK,
    AttentionDomain,
    blocked,
    is_article,
    round_k,
    top_trajectory,
)
from arena.models import Question

FAMILY = "attention-hgb"
REVISION = 1


def features(traj: Sequence[dict[str, Any]], k: float, project: str, target: date) -> list[float]:
    """Feature vector from a trajectory (oldest first), K, project and target day."""
    if not traj or traj[-1]["views"] is None:
        raise ValueError("trajectory must end with the article's views on R")
    v_r = float(traj[-1]["views"])

    def lv(row: dict[str, Any]) -> float:
        v = row["views"] if row["views"] is not None else row["floor"]
        return math.log1p(float(v or 1))

    logs = [lv(r) for r in traj]
    present = [1.0 if r["views"] is not None else 0.0 for r in traj]
    out = [math.log1p(v_r), math.log(k / v_r), float(traj[-1]["rank"] or LOW_RANK)]
    out += [logs[-1] - logs[i] for i in range(len(logs) - 1)]  # growth vs each earlier day
    out += [sum(present), float(np.std(logs)), max(logs) - logs[-1]]
    out += [1.0 if project == p else 0.0 for p in PROJECTS]
    out += [1.0 if target.weekday() == d else 0.0 for d in range(7)]
    return out


@dataclass
class AttentionModel:
    """Fitted classifier plus calibration."""

    train_end: date
    clf: HistGradientBoostingClassifier | None = None
    calib: LogisticRegression | None = None
    n_train: int = 0
    n_calib: int = 0
    base_rate: float = 0.5

    @property
    def version(self) -> str:
        """Family, revision and training cut-off."""
        return f"{FAMILY}-r{REVISION}-{self.train_end.isoformat()}"

    def raw(self, x: list[float]) -> float:
        """Uncalibrated P(YES)."""
        assert self.clf is not None
        return float(self.clf.predict_proba([x])[0, 1])

    def probability(self, q: Question, ctx: dict[str, Any]) -> float:
        """Calibrated P(YES) for an attention question."""
        assert q.threshold is not None
        x = features(ctx["top_trajectory"], q.threshold, str(q.params["project"]), q.target_date)
        p = self.raw(x)
        if self.calib is None:
            return p
        lg = math.log(max(p, 1e-4) / max(1 - p, 1e-4))
        return float(self.calib.predict_proba([[lg]])[0, 1])

    def model_hash(self) -> str:
        """Short hash for forecast meta."""
        return hashlib.sha256(f"{self.version}|{self.n_train}|{self.n_calib}".encode()).hexdigest()[
            :12
        ]


@dataclass
class Rows:
    """Training rows (X, y, reference day)."""

    x: list[list[float]] = field(default_factory=list)
    y: list[int] = field(default_factory=list)
    ref: list[date] = field(default_factory=list)


def training_rows(domain: AttentionDomain, first_ref: date, last_ref: date) -> Rows:
    """Rows for reference days first_ref..last_ref (labels from the list of R+3)."""
    rows = Rows()
    medians: dict[tuple[str, date], float] = {}
    r = first_ref
    while r <= last_ref:
        for project in PROJECTS:
            top_r = domain.source.top(project, r)
            later = domain.source.top(project, r + timedelta(days=HORIZON))
            if not top_r or not later:
                continue
            key = (project, r)
            if key not in medians:
                ratios = domain.ratios(project, r)
                if len({t for t, _ in ratios}) < 30:
                    continue
                medians[key] = statistics.median(x for _, x in ratios)
            later_views = {a.article: a.views for a in later}
            floor = min(later_views.values())
            for a in top_r:
                if not (TOP_RANK <= a.rank <= LOW_RANK) or not is_article(project, a.article):
                    continue
                if blocked(a.article, domain.blocklist):
                    continue
                k = round_k(a.views * medians[key])
                v3 = later_views.get(a.article)
                if v3 is None and k <= floor:
                    continue  # label unknown: below the list, but K is below its floor too
                label = int(v3 is not None and v3 >= k)
                traj = top_trajectory(domain.source, project, a.article, r)
                rows.x.append(features(traj, k, project, r + timedelta(days=HORIZON)))
                rows.y.append(label)
                rows.ref.append(r)
        r += timedelta(days=1)
    return rows


def _fit(x: list[list[float]], y: list[int], max_iter: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=max_iter,
        learning_rate=0.05,
        max_leaf_nodes=15,
        min_samples_leaf=40,
        random_state=0,
    ).fit(np.asarray(x), np.asarray(y))


def train(
    domain: AttentionDomain,
    first_ref: date,
    last_ref: date,
    *,
    folds: int = 2,
    fold_days: int = 14,
    gap_days: int = 3,
    max_iter: int = 150,
) -> AttentionModel:
    """Fit on reference days up to `last_ref` (labels need R+3 <= cut-off, the caller
    chooses `last_ref` accordingly); calibrate on out-of-fold predictions."""
    rows = training_rows(domain, first_ref, last_ref)
    if len(set(rows.y)) < 2:
        raise ValueError("training rows need both outcomes")
    raw, ys = [], []
    for k in range(folds, 0, -1):
        f_start = last_ref - timedelta(days=k * fold_days) + timedelta(days=1)
        f_end = f_start + timedelta(days=fold_days - 1)
        tr = [i for i, d in enumerate(rows.ref) if d < f_start - timedelta(days=gap_days)]
        te = [i for i, d in enumerate(rows.ref) if f_start <= d <= f_end]
        if len(tr) < 200 or not te or len({rows.y[i] for i in tr}) < 2:
            continue
        clf = _fit([rows.x[i] for i in tr], [rows.y[i] for i in tr], max_iter)
        ps = clf.predict_proba(np.asarray([rows.x[i] for i in te]))[:, 1]
        raw += [math.log(max(p, 1e-4) / max(1 - p, 1e-4)) for p in ps]
        ys += [rows.y[i] for i in te]
    model = AttentionModel(
        train_end=last_ref,
        clf=_fit(rows.x, rows.y, max_iter),
        n_train=len(rows.y),
        base_rate=sum(rows.y) / len(rows.y),
    )
    if len(set(ys)) == 2 and len(ys) >= 50:
        model.calib = LogisticRegression().fit([[v] for v in raw], ys)
        model.n_calib = len(ys)
    return model
