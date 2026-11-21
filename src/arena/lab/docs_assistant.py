"""'Ask the project': an extractive question-answering assistant over the project documents (T254).

Documents are split into heading-sized chunks, retrieved with BM25 and a dense embedding fused by
RRF, and the answer is the best-matching sentences of the top chunks, each cited by chunk id. No
language model writes the answer, so nothing can be invented (I5); when no chunk matches well
enough, it says so instead of guessing. It runs offline and costs nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from arena.agent.retrieval import BM25Index, Embedder, HashEmbedder, rrf, tokens

MAX_CHARS = 900
#: A question is answered only if the best chunk matches at least this share of its terms.
MIN_COVERAGE = 0.5

_STOP = frozenset(
    "a an and are as at be by do does for from how in is it of on or that the this to was what "
    "when where which who why with project".split()
)


@dataclass(frozen=True)
class Chunk:
    """One citable piece of a document."""

    chunk_id: str
    path: str
    heading: str
    text: str


@dataclass(frozen=True)
class Answer:
    """The reply: cited sentences, or a refusal."""

    refused: bool
    text: str
    citations: tuple[str, ...]


def chunk_markdown(path: str, text: str) -> list[Chunk]:
    """Split a markdown file at headings, then at paragraph breaks to at most MAX_CHARS."""
    out: list[Chunk] = []
    heading = Path(path).name
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        buf.clear()
        while body:
            piece, body = body[:MAX_CHARS], body[MAX_CHARS:]
            if body and "\n" in piece:  # cut at the last paragraph or line break
                cut = piece.rfind("\n")
                piece, body = piece[:cut], piece[cut:] + body
            if piece.strip():
                out.append(Chunk(f"{path}#{len(out) + 1}", path, heading, piece.strip()))

    for line in text.splitlines():
        if re.match(r"#{1,4} ", line):
            flush()
            heading = line.lstrip("# ").strip()
            buf.append(line)
        else:
            buf.append(line)
    flush()
    return out


def load_chunks(root: Path, paths: list[str]) -> list[Chunk]:
    """Chunks of the listed files (relative to `root`), in a stable order."""
    chunks: list[Chunk] = []
    for rel in sorted(paths):
        chunks.extend(chunk_markdown(rel, (root / rel).read_text(encoding="utf-8")))
    return chunks


def _terms(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in _STOP and len(t) > 1]


class DocsIndex:
    """BM25 + dense retrieval over chunks, fused with RRF."""

    def __init__(self, chunks: list[Chunk], embedder: Embedder | None = None) -> None:
        self.chunks = chunks
        self.embedder = embedder or HashEmbedder()
        self.bm25 = BM25Index([f"{c.heading} {c.text}" for c in chunks])
        emb = np.asarray(self.embedder.embed([f"{c.heading} {c.text}" for c in chunks]))
        self.emb = emb

    def search(self, question: str, k: int = 3) -> list[Chunk]:
        """The k best chunks for a question."""
        lex = self.bm25.scores(" ".join(_terms(question)))
        q = np.asarray(self.embedder.embed([question]))[0]
        dense = self.emb @ q
        ranks = [list(np.argsort(-lex)[:20]), list(np.argsort(-dense)[:20])]
        fused = rrf([[int(i) for i in r] for r in ranks])
        order = sorted(fused, key=lambda i: -fused[i])[:k]
        return [self.chunks[i] for i in order]

    def coverage(self, question: str, chunk: Chunk) -> float:
        """Share of the question's content words that occur in the chunk or its heading."""
        want = set(_terms(question))
        have = set(_terms(f"{chunk.heading} {chunk.text}"))
        return len(want & have) / len(want) if want else 0.0


def _sentences(text: str) -> list[str]:
    flat = re.sub(r"\s+", " ", re.sub(r"[#>*`|]", " ", text))
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat) if len(s.strip()) > 20]


def ask(index: DocsIndex, question: str, k: int = 3, min_coverage: float = MIN_COVERAGE) -> Answer:
    """Answer from the documents, cited by chunk id, or refuse when nothing matches well."""
    hits = index.search(question, k)
    if not hits or max(index.coverage(question, c) for c in hits) < min_coverage:
        return Answer(True, "Not in the documents.", ())
    want = set(_terms(question))
    scored = []
    for c in hits:
        for s in _sentences(c.text):
            overlap = len(want & set(_terms(s)))
            if overlap:
                scored.append((overlap, c.chunk_id, s))
    scored.sort(key=lambda t: -t[0])
    top = scored[:3]
    if not top:
        return Answer(True, "Not in the documents.", ())
    text = " ".join(f"{s} [{cid}]" for _, cid, s in top)
    return Answer(False, text, tuple(dict.fromkeys(cid for _, cid, _ in top)))


#: The documents the assistant reads (the written project record, not code or data).
DOC_PATHS = [
    "docs/SPEC.md",
    "docs/METHODS.md",
    "docs/RUNBOOK.md",
    "docs/COMPLIANCE.md",
    "docs/CODE_TOUR.md",
    "docs/explainers/01-ledger-and-forecast-before-truth.md",
    "docs/explainers/02-power-market-questions.md",
    "docs/explainers/03-question-design-and-base-rates.md",
    "docs/explainers/04-ml-models-leakage-calibration.md",
    "docs/explainers/05-llm-forecasters-and-agent.md",
    "docs/explainers/06-experiments-lab.md",
    "docs/explainers/06-scoring-and-statistics.md",
    "docs/explainers/07-operations-and-monitoring.md",
]


def evaluate(index: DocsIndex, pairs: list[dict[str, str | None]], k: int = 3) -> dict[str, float]:
    """Hit rate on answerable questions, refusal rate on out-of-scope ones.

    A hit needs a cited chunk that contains the expected phrase (facts live in several files)."""
    by_id = {c.chunk_id: c for c in index.chunks}
    hits = refused_ok = answerable = out_of_scope = false_refusals = 0
    for p in pairs:
        ans = ask(index, str(p["q"]), k)
        if p["source"] is None:
            out_of_scope += 1
            refused_ok += ans.refused
            continue
        answerable += 1
        false_refusals += ans.refused
        phrase = str(p["must_contain"]).lower()
        if any(phrase in by_id[c].text.lower() for c in ans.citations):
            hits += 1
    return {
        "answerable": answerable,
        "hit_pct": round(100 * hits / answerable, 1) if answerable else 0.0,
        "false_refusal_pct": round(100 * false_refusals / answerable, 1) if answerable else 0.0,
        "out_of_scope": out_of_scope,
        "correct_refusal_pct": round(100 * refused_ok / out_of_scope, 1) if out_of_scope else 0.0,
    }
