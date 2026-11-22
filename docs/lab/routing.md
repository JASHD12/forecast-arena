# Cost routing: a cheap pair first, the paid model only when they are unsure

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-routing.json`, created 2026-11-22T21:23:55Z.

Why companies use it: Routing easy cases to cheap models and escalating the rest is the standard way to cut LLM cost without losing quality.

| Variant | Questions | Brier |
|---|---|---|
| claude (llm_context) | 276 | 0.1802 |
| ml | 276 | 0.1663 |
| ft (open fine-tuned model) | 276 | 0.2474 |
| base_rate | 276 | 0.2182 |
| router (primary: pair, delta 0.15, gamma 0.10) | 276 | 0.1802 |
| curve / pair delta 0.05 | 276 | 0.1802 |
| curve / pair delta 0.10 | 276 | 0.1802 |
| curve / pair delta 0.15 | 276 | 0.1802 |
| curve / pair delta 0.20 | 276 | 0.1802 |
| curve / pair delta 0.25 | 276 | 0.1802 |
| curve / pair delta 0.30 | 276 | 0.1802 |
| curve / ml_only delta 0.05 | 276 | 0.1637 |
| curve / ml_only delta 0.10 | 276 | 0.1594 |
| curve / ml_only delta 0.15 | 276 | 0.1565 |
| curve / ml_only delta 0.20 | 276 | 0.1606 |
| curve / ml_only delta 0.25 | 276 | 0.1653 |
| curve / ml_only delta 0.30 | 276 | 0.1675 |

- router (primary) minus claude (llm_context): Brier difference +0.0000, 95% interval [+0.0000, +0.0000] over 276 questions (interval includes zero).
- router (primary) minus ml: Brier difference +0.0139, 95% interval [-0.0166, +0.0433] over 276 questions (interval includes zero).
- router (primary) minus base_rate: Brier difference -0.0379, 95% interval [-0.0590, -0.0158] over 276 questions (interval excludes zero).

- Descriptive, not pre-registered: `ml_only` at delta 0.15 escalates 66 of 276 questions (avoids 76.1% of the paid calls) with Brier 0.1565, against 0.1802 for the paid model alone and 0.1663 for `ml` alone. It was chosen after the fact from a grid of twelve points, so it is a hypothesis to test on fresh days, not a result.
- 276 questions with every forecast available; the primary rule escalates 276 of 276 (100.0%) to the paid model.
- The cheap pair is the `ml` backtest and the open fine-tuned GGUF model with its pinned calibration; the paid arm is `llm_context` (Claude Haiku).

## What this does and does not show

- Electricity only; the cheap pair is the `ml` backtest and the GGUF model, on 276 test questions from 46 days.
- The rule was fixed before the Claude answers existed; the grid is descriptive.
- The saving is counted in paid calls avoided on the shared sample, not measured live.

Paid-call cost: US$0.15.
