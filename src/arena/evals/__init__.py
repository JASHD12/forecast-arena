"""LLM evaluation harness (T124): a frozen golden set, prompt variants, metrics.

Evaluation results are never part of the live record (integrity rule I4): they live in
`evals/results/`, carry `"kind": "evaluation"` and are shown only on the "LLM evals" page.
"""
