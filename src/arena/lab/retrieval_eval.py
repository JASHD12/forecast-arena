"""Retrieval experiment (T251): dense vs BM25 vs hybrid (RRF) vs hybrid plus cross-encoder rerank.

The eval set is replayed from the power domain: a corpus of resolved past questions and a set of
later query questions. Relevance is graded deterministically from question metadata, so no one
labels anything by hand:

- grade 2: same template and entity, the document's target day within 30 days before the query's
  target day, and a threshold within 10% of the query's threshold;
- grade 1: same template (any entity) within 60 days before the query's target day;
- grade 0: everything else.

A document is eligible for a query only if it resolved strictly before the query's as-of time
(integrity rule I3), exactly as in the live retriever.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from arena.agent.retrieval import Embedder, PastQuestion, PastQuestions
from arena.evals.golden import GoldenItem


@dataclass(frozen=True)
class Meta:
    """The metadata used for grading (never shown to a retriever)."""

    template: str
    entity: str
    target: date
    threshold: float | None


def grade(query: Meta, doc: Meta) -> int:
    """Graded relevance of `doc` for `query` (2, 1 or 0)."""
    gap = (query.target - doc.target).days
    if doc.template != query.template or not 0 < gap <= 60:
        return 0
    same_threshold = (
        query.threshold is None
        or doc.threshold is None
        or abs(doc.threshold - query.threshold) <= 0.10 * abs(query.threshold)
    )
    if doc.entity == query.entity and gap <= 30 and same_threshold:
        return 2
    return 1


def dcg(gains: Sequence[int]) -> float:
    """Discounted cumulative gain with gain 2^g - 1."""
    return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranked_grades: Sequence[int], all_grades: Sequence[int], k: int) -> float | None:
    """nDCG@k; None when the query has no relevant document at all."""
    ideal = dcg(sorted(all_grades, reverse=True)[:k])
    return None if ideal == 0 else dcg(list(ranked_grades)[:k]) / ideal


def reciprocal_rank(ranked_grades: Sequence[int], min_grade: int = 2) -> float:
    """1 / rank of the first document with at least `min_grade` (0 if none in the list)."""
    for i, g in enumerate(ranked_grades, start=1):
        if g >= min_grade:
            return 1.0 / i
    return 0.0


def build_set(
    corpus_items: Sequence[GoldenItem], query_items: Sequence[GoldenItem]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Documents and graded queries from replayed questions (already filtered by window)."""
    docs: list[dict[str, Any]] = []
    metas: dict[str, Meta] = {}
    for it in corpus_items:
        q = it.question
        metas[q.question_id] = Meta(q.template, q.entity, q.target_date, q.threshold)
        docs.append(
            {
                "id": q.question_id,
                "domain": q.domain,
                "template": q.template,
                "text": q.text,
                "target_date": q.target_date.isoformat(),
                "resolved_at": q.resolve_after.isoformat(),
                "outcome": it.outcome,
            }
        )
    queries: list[dict[str, Any]] = []
    for it in query_items:
        q = it.question
        qm = Meta(q.template, q.entity, q.target_date, q.threshold)
        eligible = [d for d in docs if datetime.fromisoformat(d["resolved_at"]) < it.asof]
        grades = {d["id"]: grade(qm, metas[d["id"]]) for d in eligible}
        queries.append(
            {
                "id": q.question_id,
                "text": q.text,
                "asof": it.asof.isoformat(),
                "domain": q.domain,
                "grades": {k: v for k, v in grades.items() if v > 0},
            }
        )
    return docs, queries


def write_set(
    docs: Sequence[Mapping[str, Any]], queries: Sequence[Mapping[str, Any]], path: Path
) -> str:
    """Write the frozen eval set (one JSON object per line); returns its SHA-256."""
    lines = [json.dumps({"kind": "doc", **d}, sort_keys=True) for d in docs]
    lines += [json.dumps({"kind": "query", **q}, sort_keys=True) for q in queries]
    body = ("\n".join(lines) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return hashlib.sha256(body).hexdigest()


def read_set(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """Read the eval set back with its SHA-256."""
    body = path.read_bytes()
    docs: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []
    for line in body.decode().splitlines():
        row = json.loads(line)
        (docs if row.pop("kind") == "doc" else queries).append(row)
    return docs, queries, hashlib.sha256(body).hexdigest()


def index_of(docs: Sequence[Mapping[str, Any]], embedder: Embedder) -> PastQuestions:
    """A `PastQuestions` index over the eval documents."""
    items = [
        PastQuestion(
            d["id"],
            d["domain"],
            d["template"],
            d["text"],
            date.fromisoformat(d["target_date"]),
            datetime.fromisoformat(d["resolved_at"]),
            int(d["outcome"]),
            None,
        )
        for d in docs
    ]
    return PastQuestions(items, embedder)


def evaluate(
    index: PastQuestions,
    queries: Sequence[Mapping[str, Any]],
    arms: Mapping[str, Callable[[str, datetime, str], list[str]]],
    k: int = 5,
) -> dict[str, dict[str, float | int]]:
    """nDCG@k, MRR (first grade-2 hit), precision@k of grade-2 hits and p50 latency per arm.

    Queries without any grade-2 document are skipped (nothing to find).
    """
    out: dict[str, dict[str, float | int]] = {}
    usable = [q for q in queries if any(g == 2 for g in q["grades"].values())]
    for name, arm in arms.items():
        nd, rr, pk, lat = [], [], [], []
        for q in usable:
            t0 = time.perf_counter()
            ranked = arm(q["text"], datetime.fromisoformat(q["asof"]), q["id"])
            lat.append((time.perf_counter() - t0) * 1000)
            grades = [q["grades"].get(i, 0) for i in ranked[:k]]
            v = ndcg_at_k(grades, list(q["grades"].values()), k)
            if v is not None:
                nd.append(v)
            rr.append(reciprocal_rank(grades))
            pk.append(sum(1 for g in grades if g == 2) / k)
        n = len(usable)
        out[name] = {
            "n": n,
            "ndcg5": round(sum(nd) / len(nd), 4) if nd else 0.0,
            "mrr": round(sum(rr) / n, 4) if n else 0.0,
            "p_at_5": round(sum(pk) / n, 4) if n else 0.0,
            "latency_ms_p50": round(sorted(lat)[len(lat) // 2], 2) if lat else 0.0,
        }
    return out


def arms_for(
    index: PastQuestions, rerank: Callable[[str, Sequence[str]], Sequence[float]] | None
) -> dict[str, Callable[[str, datetime, str], list[str]]]:
    """The four compared arms; each returns ranked question ids."""

    def make(dense: bool, bm25: bool, rr: Any = None) -> Callable[[str, datetime, str], list[str]]:
        def run(text: str, asof: datetime, qid: str) -> list[str]:
            hits = index.search_hybrid(
                text, asof, k=10, exclude=qid, dense=dense, bm25=bm25, rerank=rr
            )
            return [p.question_id for p, _ in hits]

        return run

    arms = {"dense": make(True, False), "bm25": make(False, True), "hybrid_rrf": make(True, True)}
    if rerank is not None:
        arms["hybrid_rerank"] = make(True, True, rerank)
    return arms
