"""T251: BM25, RRF, hybrid search (leakage-safe) and the graded retrieval metrics."""

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from arena.agent.retrieval import BM25Index, HashEmbedder, PastQuestion, PastQuestions, rrf, tokens
from arena.lab import retrieval_eval as re_

ROOT = Path(__file__).resolve().parents[2]


def _pq(i: int, text: str, resolved: datetime) -> PastQuestion:
    return PastQuestion(f"q{i}", "power", "t", text, date(2026, 1, 1), resolved, i % 2, None)


def test_tokens_keep_numbers_whole() -> None:
    assert tokens("Will it exceed 246 EUR/MWh?") == ["will", "it", "exceed", "246", "eur", "mwh"]


def test_bm25_prefers_documents_with_the_rare_query_token() -> None:
    docs = ["peak price above 246 eur", "average price above 80 eur", "average price above 90 eur"]
    sc = BM25Index(docs).scores("price 246")
    assert sc[0] > sc[1] and sc[0] > sc[2]
    assert BM25Index(docs).scores("zzz").tolist() == [0, 0, 0]
    assert BM25Index([]).scores("x").tolist() == []


def test_rrf_rewards_agreement_and_uses_rank_positions() -> None:
    fused = rrf([[0, 1, 2], [1, 0, 2]], k=60)
    assert fused[0] == pytest.approx(1 / 61 + 1 / 62)
    assert fused[2] == pytest.approx(2 / 63)
    assert fused[0] == fused[1] > fused[2]


def test_hybrid_search_never_returns_an_ineligible_question() -> None:
    asof = datetime(2026, 3, 1, tzinfo=UTC)
    items = [
        _pq(1, "evening price above 120", datetime(2026, 2, 1, tzinfo=UTC)),
        _pq(
            2, "evening price above 120 again", datetime(2026, 3, 1, tzinfo=UTC)
        ),  # not strictly before
        _pq(3, "evening price above 120 later", datetime(2026, 4, 1, tzinfo=UTC)),  # resolved later
        _pq(4, "completely unrelated wind", datetime(2026, 1, 1, tzinfo=UTC)),
    ]
    idx = PastQuestions(items, HashEmbedder())
    for dense, bm25 in ((True, False), (False, True), (True, True)):
        hits = idx.search_hybrid("evening price above 120", asof, k=5, dense=dense, bm25=bm25)
        assert {p.question_id for p, _ in hits} <= {"q1", "q4"}
    assert idx.search_hybrid("x", asof, dense=False, bm25=False) == []
    assert idx.search_hybrid("x", datetime(2000, 1, 1, tzinfo=UTC)) == []


def test_exclude_domain_and_rerank_hooks() -> None:
    asof = datetime(2026, 3, 1, tzinfo=UTC)
    items = [_pq(i, f"question {i} price", datetime(2026, 2, 1, tzinfo=UTC)) for i in range(6)]
    idx = PastQuestions(items, HashEmbedder())
    hits = idx.search_hybrid("price", asof, k=3, exclude="q0")
    assert "q0" not in {p.question_id for p, _ in hits}
    # a fake reranker that prefers the highest question number decides the final order
    rr = idx.search_hybrid(
        "price", asof, k=3, rerank=lambda q, docs: [float(d.split()[1]) for d in docs]
    )
    assert [p.question_id for p, _ in rr] == ["q5", "q4", "q3"]


def test_grades_and_metrics() -> None:
    q = re_.Meta("max_gt", "DE_LU", date(2026, 10, 10), 300.0)
    near = re_.Meta("max_gt", "DE_LU", date(2026, 10, 1), 310.0)
    far_threshold = re_.Meta("max_gt", "DE_LU", date(2026, 10, 1), 200.0)
    other_template = re_.Meta("min_lt", "DE_LU", date(2026, 10, 1), 300.0)
    old = re_.Meta("max_gt", "DE_LU", date(2026, 7, 1), 300.0)
    assert re_.grade(q, near) == 2
    assert re_.grade(q, far_threshold) == 1
    assert re_.grade(q, other_template) == 0 and re_.grade(q, old) == 0
    assert (
        re_.grade(q, re_.Meta("max_gt", "DE_LU", date(2026, 10, 10), 300.0)) == 0
    )  # same day: not past
    assert re_.ndcg_at_k([2, 1, 0], [2, 1, 0], 3) == pytest.approx(1.0)
    assert re_.ndcg_at_k([0, 0, 2], [2, 1], 3) < 1.0
    assert re_.ndcg_at_k([0], [0, 0], 5) is None
    assert re_.reciprocal_rank([0, 1, 2]) == pytest.approx(1 / 3)
    assert re_.reciprocal_rank([0, 1]) == 0.0
    assert re_.dcg([2]) == pytest.approx(3.0) and math.isfinite(re_.dcg([]))


def test_committed_retrieval_set_and_result_are_consistent() -> None:
    path = ROOT / "evals" / "golden" / "retrieval-v1.jsonl"
    res = ROOT / "evals" / "results" / "lab-retrieval-hybrid.json"
    if not (path.is_file() and res.is_file()):
        pytest.skip("retrieval set not committed in this checkout")
    docs, queries, sha = re_.read_set(path)
    result = json.loads(res.read_text())
    assert result["dataset_sha256"]["retrieval-v1"] == sha
    # leakage: every graded document of a query resolved strictly before the query's as-of time
    resolved = {d["id"]: datetime.fromisoformat(d["resolved_at"]) for d in docs}
    for q in queries:
        asof = datetime.fromisoformat(q["asof"])
        assert all(resolved[i] < asof for i in q["grades"]), q["id"]
    assert set(result["metrics"]) == {"dense", "bm25", "hybrid_rrf", "hybrid_rerank"}
