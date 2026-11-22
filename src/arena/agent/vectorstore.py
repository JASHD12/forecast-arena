"""Past-question search on a vector database, Qdrant (T291).

`QdrantIndex` has the same `search` contract as `PastQuestions.search` (cosine similarity, the
forecast time as an upper bound, an excluded id, an optional domain), but the vectors live in a
Qdrant collection and the leakage rule is a **payload filter evaluated inside the store**:
`resolved_ts < asof` is part of every query, so a question resolved at or after the forecast time
cannot be returned however the caller behaves (rule I3). The location chooses the deployment:
`:memory:` or a directory (Qdrant local mode: tests and the lab study) or an `http://host:6333` URL
of a Qdrant server (the CI job and production-style setups).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import numpy as np

from arena.agent.retrieval import MAX_K, Embedder, PastQuestion

COLLECTION = "past_questions"


def _ts(t: datetime) -> float:
    return t.timestamp()


class QdrantIndex:
    """Dense retrieval over resolved questions with the time filter inside Qdrant."""

    def __init__(
        self,
        items: Sequence[PastQuestion],
        embedder: Embedder,
        location: str = ":memory:",
        collection: str = COLLECTION,
    ) -> None:
        from qdrant_client import QdrantClient, models

        self.items = list(items)
        self.embedder = embedder
        self.collection = collection
        self._models = models
        if location.startswith("http"):
            self.client = QdrantClient(url=location)
        elif location == ":memory:":
            self.client = QdrantClient(":memory:")
        else:
            self.client = QdrantClient(path=location)
        if not self.items:
            return
        vecs = np.asarray(embedder.embed([p.text for p in self.items]), float)
        vecs = vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-12)
        if self.client.collection_exists(collection):
            self.client.delete_collection(collection)  # the index is rebuilt from the ledger
        self.client.create_collection(
            collection,
            vectors_config=models.VectorParams(
                size=int(vecs.shape[1]), distance=models.Distance.COSINE
            ),
        )
        self.client.upsert(
            collection,
            points=[
                models.PointStruct(
                    id=i,
                    vector=vecs[i].tolist(),
                    payload={
                        "question_id": p.question_id,
                        "domain": p.domain,
                        "resolved_ts": _ts(p.resolved_at),
                    },
                )
                for i, p in enumerate(self.items)
            ],
            wait=True,
        )

    def search(
        self,
        text: str,
        asof: datetime,
        *,
        k: int = 5,
        exclude: str | None = None,
        domain: str | None = None,
    ) -> list[tuple[PastQuestion, float]]:
        """Top-k eligible past questions by cosine similarity, filtered inside the store."""
        if not self.items:
            return []
        m = self._models
        must = [m.FieldCondition(key="resolved_ts", range=m.Range(lt=_ts(asof)))]
        if domain is not None:
            must.append(m.FieldCondition(key="domain", match=m.MatchValue(value=domain)))
        must_not = (
            [m.FieldCondition(key="question_id", match=m.MatchValue(value=exclude))]
            if exclude
            else []
        )
        qv = np.asarray(self.embedder.embed([text]), float)[0]
        qv = qv / max(float(np.linalg.norm(qv)), 1e-12)
        res = self.client.query_points(
            self.collection,
            query=qv.tolist(),
            query_filter=m.Filter(must=must, must_not=must_not),
            limit=max(1, min(MAX_K, k)),
        )
        return [(self.items[int(h.id)], float(h.score)) for h in res.points]
