# Retrieval: dense vs BM25 vs hybrid with reranking

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-retrieval-hybrid.json`, created 2026-11-21T14:50:56Z.

Why companies use it: Hybrid search with reranking is the standard retrieval stack of production RAG (docs/SOURCES.md, lab sources).

| Variant | Questions | nDCG@5 | MRR | Precision@5 | Latency p50 (ms) |
|---|---|---|---|---|---|
| dense | 143 | 0.3731 | 0.5065 | 0.2126 | 51.92 |
| bm25 | 143 | 0.3386 | 0.8012 | 0.186 | 10.56 |
| hybrid_rrf | 143 | 0.3464 | 0.6656 | 0.2196 | 59.86 |
| hybrid_rerank | 143 | 0.5557 | 0.7425 | 0.3762 | 382.68 |


- 2004 resolved power questions as documents, 186 October 2026 queries; relevance is graded from template, entity, date and threshold (see the module docstring), never by hand.
- The live agent keeps its dense retriever; nothing here changes a live forecast.

## What this does and does not show

- Relevance is graded from question metadata, so it rewards matching template, entity and a similar threshold; it says nothing about whether the retrieved questions improve a forecast.
- One domain (electricity), one month of queries; queries on the same day are correlated and the differences between arms were not tested for significance.
- Cross-encoder latency is measured on a shared 2-core CPU and varies between runs.

Paid-call cost: US$0.00.
