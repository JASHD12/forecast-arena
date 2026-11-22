"""The ledger as pandas DataFrames (T301).

DuckDB (`analytics/sql.py`) and Polars (the analysis notebook) stay the engines for queries over the
open data; pandas is added because it is the interchange format of scikit-learn, of most notebooks
and of most teams. Every function here is a thin, tested view over `arena.scoring`: the numbers
must equal the leaderboard's (a test compares them), they are never a second definition of a score.

pandas is imported inside the functions, so the production jobs (which do not install it) never
load it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from arena.scoring.core import CLIP_HIGH, CLIP_LOW, Scored

COLUMNS = ("question_id", "forecaster_id", "domain", "batch_date", "probability", "outcome")


def scored_frame(scored: Sequence[Scored]) -> Any:
    """One row per resolved forecast, with the clipped Brier loss of that forecast."""
    import pandas as pd

    df = pd.DataFrame(
        [
            (s.question_id, s.forecaster_id, s.domain, s.batch_date, s.probability, s.outcome)
            for s in scored
        ],
        columns=list(COLUMNS),
    )
    df["batch_date"] = pd.to_datetime(df["batch_date"])
    p = df["probability"].clip(CLIP_LOW, CLIP_HIGH)
    df["brier"] = (p - df["outcome"]) ** 2
    return df


def leaderboard_frame(df: Any) -> Any:
    """Mean Brier and log score per forecaster, best first (same definition as `scoring.core`)."""
    p = df["probability"].clip(CLIP_LOW, CLIP_HIGH)
    log = -(df["outcome"] * np.log(p) + (1 - df["outcome"]) * np.log(1 - p))
    out = (
        df.assign(log=log)
        .groupby("forecaster_id")
        .agg(n=("question_id", "nunique"), brier=("brier", "mean"), log=("log", "mean"))
        .reset_index()
    )
    return out.sort_values(["brier", "forecaster_id"]).reset_index(drop=True)


def calibration_frame(df: Any, forecaster: str, bins: int = 5) -> Any:
    """Reliability table: bins of the stated probability, mean stated, observed frequency, count."""
    import pandas as pd

    d = df[df["forecaster_id"] == forecaster]
    cut = pd.cut(d["probability"], bins=np.linspace(0, 1, bins + 1), include_lowest=True)
    g = d.groupby(cut, observed=True).agg(
        n=("outcome", "size"), mean_p=("probability", "mean"), frequency=("outcome", "mean")
    )
    return g.reset_index().rename(columns={"probability": "bin"})


def wide_probabilities(df: Any) -> Any:
    """Questions as rows, forecasters as columns (NaN where a forecaster did not answer)."""
    return df.pivot_table(index="question_id", columns="forecaster_id", values="probability")


def rolling_brier(df: Any, forecaster: str, window: int = 7) -> Any:
    """Daily mean Brier of one forecaster and its rolling mean over `window` batch days."""
    d = df[df["forecaster_id"] == forecaster].groupby("batch_date")["brier"].mean().sort_index()
    return d.to_frame("daily").assign(rolling=d.rolling(window, min_periods=1).mean())
