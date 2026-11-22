"""T301: pandas views over the scored record equal the leaderboard; the stacking pipeline runs."""

from datetime import date, timedelta

import numpy as np
import pytest

pytest.importorskip("pandas")

from arena.analytics import frames
from arena.lab import stacking_study as st
from arena.scoring.core import Scored, leaderboard


def synthetic(n_days: int = 14, per_day: int = 8, seed: int = 0) -> list[Scored]:
    rng = np.random.default_rng(seed)
    out = []
    for d in range(n_days):
        day = date(2026, 11, 1) + timedelta(days=d)
        for k in range(per_day):
            y = int(rng.random() < 0.5)
            qid = f"{'power' if k % 2 else 'weather'}-{day}-{k}"
            dom = "power" if k % 2 else "weather"
            good = float(np.clip(0.5 + (y - 0.5) * 0.6 + rng.normal(0, 0.05), 0.02, 0.98))
            out += [
                Scored(qid, "ml", "v", dom, day, good, y),
                Scored(qid, "base_rate", "v", dom, day, 0.5, y),
                Scored(qid, "persistence", "v", dom, day, float(rng.random()), y),
            ]
    return out


def test_leaderboard_frame_equals_the_scoring_leaderboard() -> None:
    scored = synthetic()
    got = frames.leaderboard_frame(frames.scored_frame(scored)).set_index("forecaster_id")
    for row in leaderboard(scored):
        assert got.loc[row.forecaster_id, "brier"] == pytest.approx(row.brier)
        assert got.loc[row.forecaster_id, "log"] == pytest.approx(row.log)
        assert got.loc[row.forecaster_id, "n"] == row.n


def test_wide_calibration_and_rolling_views() -> None:
    df = frames.scored_frame(synthetic())
    wide = frames.wide_probabilities(df)
    assert set(wide.columns) == {"ml", "base_rate", "persistence"} and len(wide) == 14 * 8
    cal = frames.calibration_frame(df, "ml", bins=4)
    assert cal["n"].sum() == 14 * 8 and (cal["frequency"].between(0, 1)).all()
    roll = frames.rolling_brier(df, "ml", window=3)
    assert len(roll) == 14 and roll["rolling"].iloc[0] == pytest.approx(roll["daily"].iloc[0])


def test_the_stacking_pipeline_is_a_columntransformer_plus_logistic_regression() -> None:
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import LogisticRegression

    pipe = st.build_pipeline()
    assert isinstance(pipe.named_steps["features"], ColumnTransformer)
    assert isinstance(pipe.named_steps["model"], LogisticRegression)


def test_the_replay_is_walk_forward_and_stacks_better_than_the_equal_mean() -> None:
    rep = st.replay(synthetic(n_days=20, per_day=10))
    assert len(rep["y"]) > 50 and set(rep["arms"]) == {"stacking", "equal_mean", "ml"}
    # the first test day has at least LAG_DAYS of training days before it
    assert min(rep["days"]) >= "2026-11-04"
    from arena.scoring import stats

    y = rep["y"]
    b = {k: float(np.mean(stats.brier_terms(v, y))) for k, v in rep["arms"].items()}
    assert b["stacking"] < b["equal_mean"]  # the pipeline learns that ml is the informative peer
