# Pre-registration: offline prompt optimisation for the open model (T297)

Written and committed before any candidate is scored. Rule L2 of SPEC 17.

## Question

Can a better prompt (instruction wording, a few solved examples) make the **free local model**
(Qwen2.5-1.5B-Instruct, GGUF Q4_K_M, the model behind `llm_local`) forecast better than the live
prompt, with no training and no paid call?

## Method

- Scoring: single-token margin logit(YES) - logit(NO) at the start of the assistant answer
  (`arena.lab.ft_runtime.LlamaScorer`), turned into a probability by a Platt map. Same scorer
  family as the fine-tuned model, so the arms are comparable.
- Data: the frozen splits of `lab/data/forecast-sft` (power questions, replayed leak-free).
  Search uses a **validation** subsample only (48 rows, seeded, stratified by template). Worked
  examples (shots) are drawn from the **train** split only.
- Candidates (8, fixed now): 4 instruction variants x {0, 4} shots.
  - instruction 0: the live system prompt unchanged (with 0 shots this is the **baseline**);
  - 1: one-word answer rule; 2: stay near the base rate unless the recent daily values clearly
    cross the threshold; 3: compare the threshold with the last seven daily values first.
  - shots: 4 resolved train questions (question text and answer only), balanced YES and NO.
- Selection: Brier of the Platt-calibrated margins, **cross-fitted** on the 48 validation rows
  (two folds: fit on one, score on the other, and back). The candidate with the lowest
  cross-fitted Brier is the winner; ties go to the baseline.
- Final evaluation, once: the winner and the baseline are scored on the frozen test sets
  (`test_oct`, `test_nov`, 276 questions) with a Platt map fitted on the 48 validation margins of
  that same prompt. Paired day-block bootstrap intervals (`arena.scoring.stats`).

## Hypotheses

- **H-PO1:** the winner beats the baseline on the test sets (Brier difference below zero with an
  interval that excludes zero).
- **H-PO2:** the winner does **not** beat the base rate or the `ml` champion. This is the
  expected outcome for a 1.5B model.

## Decision rule

A prompt is only a *candidate* for a new versioned `llm_local` prompt if H-PO1 holds. It then
needs an owner decision and a new version string; nothing changes live because of this result
(I8). If H-PO1 fails the result is published as negative: the live prompt stays.

## Cost

US$0. CPU on GitHub-hosted runners (workflow `lab-prompt-opt.yml`, manual, no API key).
