"""Forecast Arena dashboard (T143): explore the public record with filters.

Reads the four open Parquet files, either from a local folder (`ARENA_DATA_DIR`) or from
the published site (`ARENA_DATA_URL`, default the project's GitHub Pages data folder).
Read-only; every number is computed here from those files with DuckDB and pandas.
Exploratory: the headline comparison with 95% intervals is on the site's leaderboard.

Run: streamlit run apps/dashboard/streamlit_app.py
"""

from __future__ import annotations

import os

import duckdb
import pandas as pd
import streamlit as st

DEFAULT_URL = "https://jashd12.github.io/forecast-arena/data/"
TABLES = ("questions", "forecasts", "resolutions", "skips")


@st.cache_data(ttl=3600, show_spinner="Loading the open data...")
def load() -> dict[str, pd.DataFrame]:
    """The four tables as DataFrames (local folder first, else the published site)."""
    local = os.environ.get("ARENA_DATA_DIR")
    base = local if local else os.environ.get("ARENA_DATA_URL", DEFAULT_URL)
    sep = "" if base.endswith("/") else "/"
    return {t: pd.read_parquet(f"{base}{sep}{t}.parquet") for t in TABLES}


def scored(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Every resolved forecast with its clipped Brier term."""
    con = duckdb.connect()
    for name, df in data.items():
        con.register(name, df)
    return con.sql(
        """
        SELECT q.domain, q.batch_date, f.forecaster_id, f.probability, r.outcome,
               power(least(greatest(f.probability, 0.01), 0.99) - r.outcome, 2) AS brier
        FROM forecasts f
        JOIN resolutions r USING (question_id)
        JOIN questions q USING (question_id)
        """
    ).df()


st.set_page_config(page_title="Forecast Arena dashboard", layout="wide")
st.title("Forecast Arena: explore the record")
st.caption(
    "A research project, not advice. Exploratory numbers computed from the open "
    "Parquet files; the leaderboard on the site has the 95% intervals."
)

data = load()
df = scored(data)
if df.empty:
    st.info("No resolved forecasts yet.")
    st.stop()

domains = sorted(df["domain"].unique())
forecasters = sorted(df["forecaster_id"].unique())
c1, c2 = st.columns(2)
pick_d = c1.multiselect("Topics", domains, default=domains)
pick_f = c2.multiselect("Forecasters", forecasters, default=forecasters)
view = df[df["domain"].isin(pick_d) & df["forecaster_id"].isin(pick_f)]

k1, k2, k3 = st.columns(3)
k1.metric("Questions", int(data["questions"]["question_id"].nunique()))
k2.metric("Resolved forecasts in view", len(view))
k3.metric("Days", int(view["batch_date"].nunique()))

st.subheader("Brier score by forecaster (lower is better; 0.25 = always 50%)")
board = (
    view.groupby("forecaster_id")
    .agg(n=("brier", "size"), brier=("brier", "mean"))
    .sort_values("brier")
    .reset_index()
)
st.dataframe(board, hide_index=True, use_container_width=True)

st.subheader("Running average Brier score")
daily = (
    view.groupby(["batch_date", "forecaster_id"])["brier"]
    .agg(["sum", "count"])
    .groupby(level="forecaster_id")
    .cumsum()
    .reset_index()
)
daily["running_brier"] = daily["sum"] / daily["count"]
st.line_chart(daily, x="batch_date", y="running_brier", color="forecaster_id")

st.subheader("Calibration: mean forecast vs observed YES rate")
bins = pd.cut(view["probability"], [0, 0.2, 0.4, 0.6, 0.8, 1.0], include_lowest=True)
cal = (
    view.assign(bin=bins.astype(str))
    .groupby(["forecaster_id", "bin"])
    .agg(n=("outcome", "size"), mean_forecast=("probability", "mean"), yes_rate=("outcome", "mean"))
    .reset_index()
)
st.dataframe(cal, hide_index=True, use_container_width=True)

st.subheader("Skipped forecasts (a skip is recorded instead of a guess)")
sk = data["skips"]
st.dataframe(
    sk.groupby(["forecaster_id", "reason_code"]).size().rename("n").reset_index(),
    hide_index=True,
    use_container_width=True,
)
