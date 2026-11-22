# Offline prompt optimisation for the free local model

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-prompt-opt.json`, created 2026-11-22T20:46:44Z.

Why companies use it: Prompt engineering evaluated against a baseline on a time-split set is the standard way to improve an LLM feature without training.

| Variant | Questions | Brier | Log score | ECE |
|---|---|---|---|---|
| baseline / test_oct | 186 | 0.2625 | 0.7185 | 0.128 |
| winner / test_oct | 186 | 0.2564 | 0.7063 | 0.107 |
| base_rate / test_oct | 186 | 0.2255 | 0.6406 | 0.0851 |
| ml / test_oct | 186 | 0.1814 | 0.5219 | 0.1177 |
| baseline / test_nov | 90 | 0.2648 | 0.7234 | 0.0706 |
| winner / test_nov | 90 | 0.2539 | 0.701 | 0.0794 |
| base_rate / test_nov | 90 | 0.203 | 0.588 | 0.0564 |
| ml / test_nov | 90 | 0.1352 | 0.4376 | 0.1741 |
| baseline / test_all | 276 | 0.2632 | 0.7201 | 0.1208 |
| winner / test_all | 276 | 0.2556 | 0.7045 | 0.094 |
| base_rate / test_all | 276 | 0.2182 | 0.6235 | 0.0591 |
| ml / test_all | 276 | 0.1663 | 0.4944 | 0.0673 |

- winner minus baseline: Brier difference -0.0060, 95% interval [-0.0131, +0.0015] over 186 questions (interval includes zero).
- winner minus base_rate: Brier difference +0.0309, 95% interval [+0.0186, +0.0422] over 186 questions (interval excludes zero).
- winner minus ml: Brier difference +0.0750, 95% interval [+0.0288, +0.1170] over 186 questions (interval excludes zero).
- winner minus baseline: Brier difference -0.0109, 95% interval [-0.0204, -0.0014] over 90 questions (interval excludes zero).
- winner minus base_rate: Brier difference +0.0509, 95% interval [+0.0263, +0.0738] over 90 questions (interval excludes zero).
- winner minus ml: Brier difference +0.1188, 95% interval [+0.0549, +0.1636] over 90 questions (interval excludes zero).
- winner minus baseline: Brier difference -0.0076, 95% interval [-0.0135, -0.0017] over 276 questions (interval excludes zero).
- winner minus base_rate: Brier difference +0.0375, 95% interval [+0.0267, +0.0488] over 276 questions (interval excludes zero).
- winner minus ml: Brier difference +0.0893, 95% interval [+0.0537, +0.1236] over 276 questions (interval excludes zero).

- Winner of the search: i3s0 (baseline i0s0). Search log, cross-fitted Brier on the 48 validation questions per candidate (i = instruction variant, s = solved examples): i0s0 0.2753, i1s0 0.2722, i2s0 0.2581, i3s0 0.2573, i0s4 0.3003, i1s4 0.2781, i2s4 0.2652, i3s4 0.2619.
- Platt maps are fitted on the 48 validation margins of each prompt; the test sets are scored once.

## What this does and does not show

- Electricity only; 276 test questions from 46 days; intervals are wide.
- Eight candidates only, searched on 48 validation questions: a small search.
- One model (Qwen2.5-1.5B-Instruct Q4_K_M); the result does not transfer to Claude.

Paid-call cost: US$0.00.
