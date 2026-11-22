"""Stacking with a scikit-learn Pipeline on pandas DataFrames, replayed on the live record (T301).

A `ColumnTransformer` turns each question's peer forecasts (logits) and its domain (one-hot) into a
feature matrix and a logistic regression stacks them. It is refitted every batch day on questions of
days at least two days earlier (outcomes known) and answers the questions of that day; compared on
identical questions with the Hedge blend of `bandit_study`, the equal-weight mean and `ml`. It
exists to show the DataFrame-based modelling stack end to end, not to propose a new forecaster.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Any

import numpy as np

from arena.analytics.frames import scored_frame, wide_probabilities
from arena.scoring.core import Scored

PEERS = ("ml", "base_rate", "persistence")  # the forecasters that answer every question
LAG_DAYS = 2
MIN_TRAIN = 40


def _logit(p: Any) -> Any:
    q = np.clip(p, 0.01, 0.99)
    return np.log(q / (1 - q))


def build_pipeline() -> Any:
    """ColumnTransformer (peer logits, domain one-hot) followed by a logistic regression."""
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import FunctionTransformer, OneHotEncoder

    pre = ColumnTransformer(
        [
            ("logits", FunctionTransformer(_logit, feature_names_out="one-to-one"), list(PEERS)),
            ("domain", OneHotEncoder(handle_unknown="ignore"), ["domain"]),
        ]
    )
    return Pipeline([("features", pre), ("model", LogisticRegression(C=1.0, max_iter=500))])


def frame(scored: Sequence[Scored]) -> Any:
    """Questions with all peers answered: wide probabilities, domain, batch day and outcome."""
    df = scored_frame([s for s in scored if s.forecaster_id in PEERS])
    wide = wide_probabilities(df)
    meta = df.drop_duplicates("question_id").set_index("question_id")[
        ["domain", "batch_date", "outcome"]
    ]
    out = wide.join(meta, how="inner")
    complete = out.dropna(subset=list(PEERS))
    # a peer that never answers must not empty the study: keep the peers that exist
    return complete


def replay(scored: Sequence[Scored]) -> dict[str, Any]:
    """Walk-forward stacking probabilities and the equal-weight mean for the same questions."""
    data = frame(scored)
    if data.empty:
        return {"ids": [], "days": [], "y": [], "arms": {}}
    days = sorted(data["batch_date"].unique())
    ids: list[str] = []
    rows: dict[str, list[float]] = {"stacking": [], "equal_mean": [], "ml": []}
    dd: list[str] = []
    yy: list[int] = []
    for day in days:
        cutoff = day - timedelta(days=LAG_DAYS)
        train = data[data["batch_date"] <= cutoff]
        test = data[data["batch_date"] == day]
        if len(train) < MIN_TRAIN or train["outcome"].nunique() < 2:
            continue
        model = build_pipeline().fit(train[[*PEERS, "domain"]], train["outcome"])
        p = model.predict_proba(test[[*PEERS, "domain"]])[:, 1]
        for qid, prob, (_, row) in zip(test.index, p, test.iterrows(), strict=True):
            ids.append(str(qid))
            rows["stacking"].append(float(prob))
            rows["equal_mean"].append(float(np.mean([row[e] for e in PEERS])))
            rows["ml"].append(float(row["ml"]))
            dd.append(str(day)[:10])
            yy.append(int(row["outcome"]))
    return {"ids": ids, "days": dd, "y": yy, "arms": rows}
