"""T291: the Qdrant index returns what brute force returns and enforces the leakage rule itself."""

import os
from datetime import UTC, date, datetime, timedelta

import pytest

pytest.importorskip("qdrant_client")

from arena.agent.retrieval import HashEmbedder, PastQuestion, PastQuestions
from arena.agent.vectorstore import QdrantIndex

BASE = datetime(2026, 10, 1, 7, tzinfo=UTC)


def items(n: int = 40) -> list[PastQuestion]:
    out = []
    for i in range(n):
        d = BASE + timedelta(days=i)
        text = f"Will the {['mean', 'max', 'min'][i % 3]} price on day {i} top {50 + i} EUR?"
        out.append(
            PastQuestion(
                f"q{i:03d}",
                "power" if i % 2 else "weather",
                "mean_gt",
                text,
                date(2026, 10, 2) + timedelta(days=i),
                d,
                i % 2,
                None,
            )
        )
    return out


#: local mode always; a Qdrant server too when the CI job `vectordb` sets ARENA_QDRANT_URL
LOCATIONS = [
    ":memory:",
    *([os.environ["ARENA_QDRANT_URL"]] if os.environ.get("ARENA_QDRANT_URL") else []),
]


@pytest.fixture(scope="module", params=LOCATIONS)
def both(request):
    emb = HashEmbedder()
    its = items()
    return PastQuestions(its, emb), QdrantIndex(its, emb, request.param)


def test_top_k_similarities_match_brute_force(both) -> None:
    """The k best similarities agree (the order of exact ties may differ between the stores)."""
    brute, qd = both
    asof = BASE + timedelta(days=30)
    for text in ("Will the mean price on day 7 top 60 EUR?", "max price day 21", "min price"):
        a = brute.search(text, asof, k=5)
        b = qd.search(text, asof, k=5)
        assert [s for _, s in a] == pytest.approx([s for _, s in b], abs=1e-4)
        best = {p.question_id for p, s in a if s > a[-1][1] + 1e-6}  # strictly above the cut-off
        assert best <= {p.question_id for p, _ in b}


def test_the_store_itself_refuses_questions_resolved_at_or_after_asof(both) -> None:
    _, qd = both
    asof = BASE + timedelta(days=10)
    hits = qd.search("Will the mean price on day 12 top 62 EUR?", asof, k=20)
    assert hits and all(p.resolved_at < asof for p, _ in hits)
    assert qd.search("anything", BASE - timedelta(days=1)) == []  # nothing had resolved yet


def test_domain_filter_and_excluded_id(both) -> None:
    _, qd = both
    asof = BASE + timedelta(days=39)
    hits = qd.search("Will the mean price on day 3 top 53 EUR?", asof, k=10, domain="power")
    assert hits and all(p.domain == "power" for p, _ in hits)
    top = qd.search("Will the mean price on day 3 top 53 EUR?", asof, k=3)[0][0].question_id
    again = qd.search("Will the mean price on day 3 top 53 EUR?", asof, k=3, exclude=top)
    assert top not in [p.question_id for p, _ in again]


def test_an_empty_index_returns_nothing() -> None:
    assert QdrantIndex([], HashEmbedder()).search("x", BASE) == []
