# Pre-registration: distillation from Claude into the open 1.5B model (T247)

Experiment id: `distill`. Registered 2026-11-22, before any label exists (SPEC 17, rule L2). Owner approval of the paid label run:
HUMAN_TODO H27 (2026-11-22).

## Question

Can a small open model, trained on a teacher's probabilities (soft labels) instead of the hard outcomes, match the teacher's quality at a
fraction of the cost per 1,000 questions?

## Method

- Teacher: the live forecaster model (Claude Haiku) with the live prompt, one call per question, no tools. Labels for 1,200 seeded,
  template-balanced **training-split** questions only (`arena lab distill-labels`, workflow `lab-distill-labels.yml`); hard caps of
  1,300 requests and 2.2M tokens; list-price estimate about US$0.35. Only the probability is stored (not the rationale text).
- Student: Qwen2.5-1.5B-Instruct with the QLoRA recipe of `lab-qlora-r1` (same data windows, adapter, seed, budget) with the loss on the
  YES/NO margin replaced by the binary cross-entropy against the teacher probability. The Platt map is fitted on the validation split only.
- Evaluation: the 276 frozen test questions, paired day-block intervals against the teacher, the QLoRA model, the untuned model, the base
  rate and `ml`; cost per 1,000 questions (teacher at list price, student at US$0 on CPU) and CPU seconds per question.

## Hypotheses

- **H-DS1**: the student is closer to the teacher than the hard-label QLoRA model is (smaller mean absolute difference of probabilities).
- **H-DS2**: the student does not beat the plain base rate on the test sets (same expected negative result as QLoRA and DPO).
- **H-DS3**: the teacher itself is not better than the base rate on these questions (it was not in the earlier 24-question eval).

## Decision rule

Whatever the numbers, they are published with intervals. Nothing changes live (I8). The student's training run is the owner's Colab
step (a later H item) and happens only after the labels are committed.
