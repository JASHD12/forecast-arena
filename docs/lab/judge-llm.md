# Two LLM judges compared (not human calibration)

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-judge-llm.json`, created 2026-11-23T20:28:49Z.

Why companies use it: Checking a judge against a second, independent model is a cheap sanity check before (and never instead of) calibrating it against human labels.

| Variant | Questions | Weighted kappa | Exact match % |
|---|---|---|---|
| agreement / data_use | 30 | 0.796 | 50.0 |
| agreement / direction | 30 | 0.75 | 50.0 |
| agreement / hedging | 30 | 0.756 | 76.7 |


- Claude Haiku 5.5 (first judge) against Claude Sonnet 5.5 (second judge) on 30 rationales both graded.
- Both are language models; this is not agreement with a human.

## What this does and does not show

- Two models can share biases, so agreement does not show either is right.
- Only the items both judges graded are compared; the sample is small.
- Both judges are from the same model family, so shared biases are likely; neither is a human.

Paid-call cost: US$0.13.
