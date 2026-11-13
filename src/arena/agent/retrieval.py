"""Retrieval of similar past questions for the agent (T120, the RAG tool).

The agent can ask for the past questions most similar to the one it is forecasting and
see how they resolved. Text embeddings come from a small local ONNX model (`fastembed`,
no API cost); similarity is cosine over unit vectors.

Leakage rule (integrity rule I3): a past question is eligible only if its first
resolution was recorded *strictly before* the forecast time and it is not voided out of
scoring. Questions still open at the forecast time, and questions resolved later, are
never returned, whatever their similarity. The question being forecast is excluded.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from arena.ledger import Ledger
from arena.scoring.core import excluded, load

#: The fastembed model (ONNX, 384 dimensions); see docs/SOURCES.md.
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
MAX_K = 10


class Embedder(Protocol):
    """Turns texts into vectors (one row per text)."""

    name: str

    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder, for tests only (no model download)."""

    name = "hash-bow-256"

    def __init__(self, dims: int = 256) -> None:
        self.dims = dims

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Count hashed lowercase word tokens into `dims` buckets."""
        out = np.zeros((len(texts), self.dims))
        for i, t in enumerate(texts):
            for w in re.findall(r"[a-z0-9]+", t.lower()):
                h = int(hashlib.sha256(w.encode()).hexdigest()[:8], 16)
                out[i, h % self.dims] += 1.0
        return out


class FastEmbedder:
    """Local ONNX sentence embeddings via fastembed (weights cached under `cache_dir`)."""

    def __init__(self, model: str = EMBED_MODEL, cache_dir: Path | None = None) -> None:
        from fastembed import TextEmbedding

        self.name = model
        cache = str(cache_dir) if cache_dir else None
        self._model = TextEmbedding(model_name=model, cache_dir=cache)

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Embed texts in one batch."""
        return np.asarray(list(self._model.embed(list(texts))), float)


def _unit(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return np.divide(m, norms, out=np.zeros_like(m), where=norms > 0)


@dataclass(frozen=True)
class PastQuestion:
    """A resolved question as the retriever sees it."""

    question_id: str
    domain: str
    template: str
    text: str
    target_date: date
    resolved_at: datetime
    outcome: int
    observed_value: float | None


class PastQuestions:
    """A vector index over resolved questions, queried with a forecast time."""

    def __init__(self, items: Sequence[PastQuestion], embedder: Embedder) -> None:
        self.items = list(items)
        self.embedder = embedder
        self._vecs = (_unit(embedder.embed([p.text for p in self.items]))
                      if self.items else np.zeros((0, 1)))  # fmt: skip

    @classmethod
    def from_ledger(cls, ledger: Ledger, embedder: Embedder) -> PastQuestions:
        """Every question with a first resolution that is not voided out of scoring."""
        rec = load(ledger)
        items = []
        for qid, res in rec.resolutions.items():
            q = rec.questions.get(qid)
            if q is None or excluded(rec, qid):
                continue
            items.append(
                PastQuestion(qid, q.domain, q.template, q.text, q.target_date,
                             res.resolved_at, res.outcome, res.observed_value)
            )  # fmt: skip
        items.sort(key=lambda p: (p.resolved_at, p.question_id))
        return cls(items, embedder)

    def search(
        self, text: str, asof: datetime, *, k: int = 5, exclude: str | None = None,
        domain: str | None = None,
    ) -> list[tuple[PastQuestion, float]]:  # fmt: skip
        """Top-k eligible past questions by cosine similarity (ties by id)."""
        k = max(1, min(MAX_K, k))
        ok = [i for i, p in enumerate(self.items)
              if p.resolved_at < asof and p.question_id != exclude
              and (domain is None or p.domain == domain)]  # fmt: skip
        if not ok:
            return []
        qv = _unit(self.embedder.embed([text]))[0]
        sims = self._vecs[ok] @ qv
        order = sorted(
            range(len(ok)), key=lambda j: (-float(sims[j]), self.items[ok[j]].question_id)
        )
        return [(self.items[ok[j]], float(sims[j])) for j in order[:k]]

    def tool_result(
        self, text: str, asof: datetime, *, k: int, exclude: str, domain: str | None
    ) -> dict[str, Any]:
        """JSON-ready result for the agent tool, with the YES rate of the matches."""
        hits = self.search(text, asof, k=k, exclude=exclude, domain=domain)
        yes = sum(p.outcome for p, _ in hits)
        return {
            "eligible_rule": "questions resolved before the forecast time only",
            "matches": [
                {
                    "question": p.text,
                    "target_date": p.target_date.isoformat(),
                    "outcome": "YES" if p.outcome else "NO",
                    "observed_value": p.observed_value,
                    "similarity": round(s, 3) if math.isfinite(s) else None,
                }
                for p, s in hits
            ],
            "yes_rate_of_matches": round(yes / len(hits), 3) if hits else None,
            "embedder": self.embedder.name,
        }
