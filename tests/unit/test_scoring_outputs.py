"""One ledger fixture checks scoring eligibility across every derived public surface."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest
from factories import B, forecast, question, resolution

from arena.analytics.sql import connect, export_parquet, run_dbt_marts, run_queries
from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.mcp_server import Benchmark
from arena.models import Void
from arena.scoring.core import leaderboard, load
from arena.site.api import LeaderboardFile, QuestionsFile
from arena.site.build import build_site

MARTS = Path(__file__).resolve().parents[2] / "analytics" / "dbt" / "models" / "marts"
NOW = datetime(2026, 11, 20, tzinfo=UTC)


@pytest.fixture
def eligibility_ledger(tmp_path):
    led = Ledger(tmp_path / "ledger")
    qs = {name: question(entity=name) for name in ("ordinary", "bug", "revised")}
    led.append(layout.questions_path(B), list(qs.values()))
    probabilities = {"ordinary": 0.999, "bug": 0.9, "revised": 0.2}
    fs = [forecast(q, "base_rate", 0.5) for q in qs.values()]
    fs += [forecast(q, "ml", probabilities[name]) for name, q in qs.items()]
    led.append(layout.forecasts_path(B), fs)
    led.append(
        layout.resolutions_path(B),
        [resolution(q, int(name == "ordinary")) for name, q in qs.items()],
    )
    led.append(
        layout.resolutions_path(B + timedelta(days=1)),
        [
            Void(
                question_id=qs[name].question_id,
                reason_code=reason,
                detail="append-only correction",
                voided_at=NOW - timedelta(days=1),
            )
            for name, reason in (("bug", "bug"), ("revised", "source_revised"))
        ],
    )
    return led, qs


def test_sql_dbt_and_parquet_agree_with_scoring_eligibility(eligibility_ledger, tmp_path) -> None:
    led, qs = eligibility_ledger
    before = {p: led.read_bytes(p) for p in led.list_files()}
    rec = load(led)
    expected_ids = {qs[name].question_id for name in ("ordinary", "revised")}
    assert {s.question_id for s in rec.scored} == expected_ids
    expected = {r.forecaster_id: r for r in leaderboard(rec.scored)}
    con = connect(rec)
    assert {
        r[0] for r in con.execute("SELECT question_id FROM resolutions").fetchall()
    } == expected_ids
    rows = {r["q"].slug: r["rows"] for r in run_queries(con)}
    for _, fid, n, score in rows["brier-by-forecaster-domain"]:
        assert n == expected[fid].n == 2
        assert score == round(expected[fid].brier, 4)
    marts = {m["name"]: m for m in run_dbt_marts(con, MARTS)}
    for fid, _, n, score in marts["mart_forecaster_topic"]["rows"]:
        assert n == expected[fid].n
        assert score == pytest.approx(expected[fid].brier)
    export_parquet(con, tmp_path)
    from_parquet = duckdb.sql(
        f"SELECT f.forecaster_id, count(*), "
        f"avg(power(least(greatest(f.probability, 0.01), 0.99) - r.outcome, 2)) "
        f"FROM '{tmp_path / 'forecasts.parquet'}' f "
        f"JOIN '{tmp_path / 'resolutions.parquet'}' r USING (question_id) GROUP BY ALL"
    ).fetchall()
    for fid, n, score in from_parquet:
        assert n == expected[fid].n
        assert score == pytest.approx(expected[fid].brier)
    assert {p: led.read_bytes(p) for p in led.list_files()} == before


def test_site_json_and_mcp_preserve_revised_outcome_and_report_missing_members(
    eligibility_ledger, tmp_path
) -> None:
    led, qs = eligibility_ledger
    result = build_site(led, tmp_path / "site", FixedClock(NOW))
    base = result.out_dir / "api" / "v1"
    data = QuestionsFile.model_validate_json((base / "questions.json").read_text())
    by = {q.question_id: q for q in data.questions}
    assert by[qs["ordinary"].question_id].status == "resolved"
    assert by[qs["bug"].question_id].status == "void"
    assert by[qs["bug"].question_id].outcome is None
    revised = by[qs["revised"].question_id]
    assert revised.status == "resolved" and revised.outcome == 0
    assert revised.revision_reason == "source_revised"
    assert by[qs["ordinary"].question_id].revision_reason is None
    lb = LeaderboardFile.model_validate_json((base / "leaderboard.json").read_text())
    # The API intentionally remains the all-questions board, while the common set is empty.
    assert {r.forecaster_id for r in lb.rows} == {"base_rate", "ml"}
    assert all(r.n == 2 for r in lb.rows)
    # T206: the common block is the home page's board (here an incomplete common set)
    assert lb.common is not None
    assert lb.common.rows == [] and lb.common.questions == 0
    assert set(lb.common.missing_forecasters) == {"llm_context", "agent"}
    html = (result.out_dir / "leaderboard.html").read_text()
    assert "Incomplete common set: no scored forecasts from llm_context, agent" in html
    assert 'class="podium"' not in html
    bug_page = (result.out_dir / "questions" / f"{qs['bug'].question_id}.html").read_text()
    assert 'class="verdict verdict-void"' in bug_page
    assert "Who was closest?" not in bug_page and 'class="score"' not in bug_page
    revised_page = (result.out_dir / "questions" / f"{qs['revised'].question_id}.html").read_text()
    assert "Who was closest?" in revised_page and 'class="score"' in revised_page
    assert "Source revision warning" in revised_page
    from arena.site.shaping import _rows, domain_stats
    from arena.site.topics import topic

    rec = load(led)
    rows, _ = _rows(list(qs.values()), rec)
    by_row = {r["qid"]: r for r in rows}
    assert by_row[qs["bug"].question_id]["state"] == "void (bug)"
    assert by_row[qs["bug"].question_id]["outcome"] is None
    assert by_row[qs["revised"].question_id]["outcome"] == 0
    assert domain_stats(rec)[0]["resolved"] == 2
    assert topic(qs["ordinary"].domain, rec)["n_resolved"] == 2
    home = (result.out_dir / "index.html").read_text()
    assert "Still missing scored forecasts from" in home and 'class="st-list"' not in home
    benchmark = Benchmark(led)
    revised_mcp = benchmark.get_question(qs["revised"].question_id)
    assert revised_mcp["status"] == "resolved" and revised_mcp["outcome"] == "NO"
    assert revised_mcp["revision_reason"] == "source_revised"
    bug_mcp = benchmark.get_question(qs["bug"].question_id)
    assert bug_mcp["status"] == "void" and bug_mcp["outcome"] is None


def test_rest_matches_static_eligibility_and_keeps_all_questions_board(eligibility_ledger) -> None:
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from arena.api.app import create_app

    led, qs = eligibility_ledger
    client = TestClient(create_app(led))
    resolved = client.get("/questions", params={"status": "resolved"}).json()
    assert {q["question_id"] for q in resolved} == {
        qs[name].question_id for name in ("ordinary", "revised")
    }
    revised = client.get(f"/questions/{qs['revised'].question_id}").json()
    assert revised["outcome"] == 0 and revised["revision_reason"] == "source_revised"
    bug = client.get(f"/questions/{qs['bug'].question_id}").json()
    assert bug["status"] == "void" and bug["outcome"] is None
    lb = client.get("/leaderboard").json()
    assert {r["forecaster_id"] for r in lb["rows"]} == {"base_rate", "ml"}
    assert all(r["n"] == 2 for r in lb["rows"])
    sql = client.get("/sql", params={"q": "SELECT count(*) FROM resolutions"}).json()
    assert sql["rows"] == [[2]]


def test_api_common_block_matches_the_board() -> None:
    """T206: rows, counts and label of `common` are taken from the same Board object."""
    from datetime import UTC, datetime
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from arena.scoring.boards import Board
    from arena.scoring.core import Record
    from arena.site.api import LeaderboardFile, build_api

    board = Board("common", "overall", ["agent", "base_rate"], 0, 0, label="too early to tell")
    with TemporaryDirectory() as d:
        build_api(
            Path(d), Record({}, {}, {}, [], []), None, "rehearsal",
            datetime(2026, 11, 19, tzinfo=UTC), lambda q: q, board,
        )  # fmt: skip
        lb = LeaderboardFile.model_validate_json((Path(d) / "api/v1/leaderboard.json").read_text())
    assert lb.common is not None and lb.common.label == board.label
    assert lb.common.forecasters == board.forecasters and lb.rows == []
