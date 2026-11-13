from datetime import UTC, datetime
from types import SimpleNamespace

import duckdb
from factories import forecast, question

from arena.analytics.sql import QUERIES, TABLES, connect, export_parquet, run_queries
from arena.models import Evidence, Resolution


def _rec(with_data: bool):
    if not with_data:
        return SimpleNamespace(questions={}, forecasts=[], resolutions={}, skips=[])
    q = question()
    fs = [forecast(q, "base_rate", 0.8), forecast(q, "ml", 0.3)]
    r = Resolution(
        question_id=q.question_id,
        outcome=1,
        observed_value=90.0,
        resolved_at=datetime(2026, 11, 14, tzinfo=UTC),
        evidence=Evidence(source_url="x://", snapshot_sha256="a" * 64, values_used={}),
    )
    return SimpleNamespace(
        questions={q.question_id: q}, forecasts=fs, resolutions={q.question_id: r}, skips=[]
    )


def test_empty_ledger_gives_empty_tables_and_results(tmp_path) -> None:
    con = connect(_rec(False))
    for name in TABLES:
        assert con.execute(f"SELECT count(*) FROM {name}").fetchone() == (0,)
    assert all(r["rows"] == [] for r in run_queries(con))
    assert sorted(export_parquet(con, tmp_path)) == sorted(f"{t}.parquet" for t in TABLES)


def test_brier_query_matches_hand_computation_and_parquet_round_trip(tmp_path) -> None:
    con = connect(_rec(True))
    res = {r["q"].slug: r for r in run_queries(con)}
    rows = {row[1]: row for row in res["brier-by-forecaster-domain"]["rows"]}
    assert rows["base_rate"][3] == round((0.8 - 1) ** 2, 4)
    assert rows["ml"][3] == round((0.3 - 1) ** 2, 4)
    assert res["yes-rate-by-template"]["rows"] == [("power", "mean_gt", 1, 1.0)]
    export_parquet(con, tmp_path)
    back = duckdb.sql(f"SELECT count(*) FROM '{tmp_path / 'forecasts.parquet'}'").fetchone()
    assert back == (2,)
    assert len(QUERIES) == len({q.slug for q in QUERIES})
