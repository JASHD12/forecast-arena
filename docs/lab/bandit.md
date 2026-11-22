# Online learning of which forecaster to trust (Hedge and Thompson sampling)

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-bandit.json`, created 2026-11-22T10:20:19Z.

Why companies use it: Expert-advice and bandit methods are the production form of reinforcement learning for choosing between models from delayed feedback.

| Variant | Questions | Brier |
|---|---|---|
| hedge | 131 | 0.1291 |
| equal_mean | 131 | 0.1548 |
| thompson | 131 | 0.1482 |
| base_rate | 131 | 0.2931 |
| ml | 131 | 0.107 |
| llm_plain | 48 | 0.2185 |
| llm_context | 47 | 0.1608 |
| agent | 47 | 0.1433 |
| best_expert_in_hindsight | 131 | 0.107 |

- hedge minus equal_mean: Brier difference -0.0257, 95% interval [-0.0363, -0.0098] over 131 questions (interval excludes zero).
- hedge minus ml: Brier difference +0.0221, 95% interval [-0.0011, +0.0407] over 131 questions (interval includes zero).
- hedge minus thompson: Brier difference -0.0191, 95% interval [-0.0370, -0.0075] over 131 questions (interval excludes zero).

- 146 live questions answered by at least two experts over 8 batch days (the live rehearsal record, replayed walk-forward with a two-day outcome lag).
- The best expert in hindsight is ml.

## What this does and does not show

- The live record is only a few days long: the weights barely move and every interval is wide. This is a mechanism check, not evidence that the blend helps.
- The best expert in hindsight is a reference, not something that could be played.

Paid-call cost: US$0.00.
