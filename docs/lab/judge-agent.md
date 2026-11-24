# LLM judge against the agent's own ratings (not human calibration)

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-judge-agent.json`, created 2026-11-23T19:27:33Z.

Why companies use it: Checking a judge against a second, independent model is a cheap sanity check before (and never instead of) calibrating it against human labels.

| Variant | Questions | Weighted kappa | Exact match % |
|---|---|---|---|
| agreement / data_use | 30 | 0.771 | 43.3 |
| agreement / direction | 30 | 0.767 | 66.7 |
| agreement / hedging | 30 | 0.723 | 66.7 |


- Claude Haiku judge (the live judge run) against agent rater (the coding assistant, ratings written by reading each card; not a human) on 30 rationales both graded.
- Both are language models; this is not agreement with a human.

## What this does and does not show

- Two models can share biases, so agreement does not show either is right.
- Only the items both judges graded are compared; the sample is small.
- The rater is the same AI coding assistant that built this project and is in the same model family as the forecasters, so its ratings carry the same blind spots; it was not blind to the judge, because it had seen some of the judge's scores earlier in the session.
- These ratings do not replace the 30 human labels, which stay open.

Paid-call cost: US$0.00.
