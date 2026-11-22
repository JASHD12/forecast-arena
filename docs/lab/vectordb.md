# Vector database: Qdrant against brute-force dense search

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-vectordb.json`, created 2026-11-22T10:29:57Z.

Why companies use it: A vector database is the standard retrieval store of production RAG systems.

| Variant | Questions | nDCG@5 | MRR | Precision@5 | Latency p50 (ms) |
|---|---|---|---|---|---|
| dense_numpy | 143 | 0.3731 | 0.5065 | 0.2126 | 39.94 |
| dense_qdrant | 143 | 0.3731 | 0.5065 | 0.2126 | 96.04 |


- 2004 documents and 143 queries of the frozen retrieval set, the same embedder for both arms; Qdrant location `:memory:` (local mode, no server).
- The forecast-time rule (a document must have resolved before the query's as-of time) is a payload filter inside Qdrant and is covered by unit tests.

## What this does and does not show

- Local mode scans vectors like brute force, so its latency says nothing about a server with an HNSW index; the CI job `vectordb` runs the same tests against a Qdrant server container.
- Two thousand documents are far below the size where an approximate index matters.

Paid-call cost: US$0.00.
