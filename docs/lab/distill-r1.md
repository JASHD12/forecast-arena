# Distillation from Claude into Qwen2.5-1.5B (soft-label QLoRA)

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-distill-r1.json`, created 2026-11-23T01:29:47Z.

Why companies use it: Distilling a large model's probabilities into a small one is the standard way to cut inference cost; the comparison with the teacher and a classical model shows what is kept.

| Variant | Questions | Brier | Log score | ECE |
|---|---|---|---|---|
| base_1_5b / test_oct | 186 | 0.249 | 0.6912 | 0.0817 |
| distill_1_5b / test_oct | 186 | 0.2363 | 0.6654 | 0.0759 |
| qlora_1_5b / test_oct | 186 | 0.24 | 0.6729 | 0.0902 |
| claude_teacher / test_oct | 186 | 0.201 | 0.5787 | 0.0665 |
| base_rate / test_oct | 186 | 0.2255 | 0.6406 | 0.0851 |
| ml / test_oct | 186 | 0.1814 | 0.5219 | 0.1177 |
| base_1_5b / test_nov | 90 | 0.2477 | 0.6886 | 0.0491 |
| distill_1_5b / test_nov | 90 | 0.237 | 0.6668 | 0.0826 |
| qlora_1_5b / test_nov | 90 | 0.233 | 0.6586 | 0.1175 |
| claude_teacher / test_nov | 90 | 0.1374 | 0.4351 | 0.094 |
| base_rate / test_nov | 90 | 0.203 | 0.588 | 0.0564 |
| ml / test_nov | 90 | 0.1352 | 0.4376 | 0.1741 |
| base_1_5b / test_all | 276 | 0.2486 | 0.6904 | 0.0585 |
| distill_1_5b / test_all | 276 | 0.2365 | 0.6658 | 0.0522 |
| qlora_1_5b / test_all | 276 | 0.2378 | 0.6683 | 0.0687 |
| claude_teacher / test_all | 276 | 0.1802 | 0.5318 | 0.05 |
| base_rate / test_all | 276 | 0.2182 | 0.6235 | 0.0591 |
| ml / test_all | 276 | 0.1663 | 0.4944 | 0.0673 |

- distill_1_5b minus base_1_5b: Brier difference -0.0128, 95% interval [-0.0177, -0.0075] over 186 questions (interval excludes zero).
- distill_1_5b minus qlora_1_5b: Brier difference -0.0037, 95% interval [-0.0078, +0.0003] over 186 questions (interval includes zero).
- distill_1_5b minus claude_teacher: Brier difference +0.0353, 95% interval [+0.0150, +0.0546] over 186 questions (interval excludes zero).
- distill_1_5b minus base_rate: Brier difference +0.0108, 95% interval [-0.0015, +0.0228] over 186 questions (interval includes zero).
- distill_1_5b minus ml: Brier difference +0.0549, 95% interval [+0.0088, +0.0962] over 186 questions (interval excludes zero).
- claude_teacher minus base_rate: Brier difference -0.0246, 95% interval [-0.0493, +0.0012] over 186 questions (interval includes zero).
- claude_teacher minus ml: Brier difference +0.0195, 95% interval [-0.0213, +0.0604] over 186 questions (interval includes zero).
- qlora_1_5b minus base_rate: Brier difference +0.0145, 95% interval [+0.0021, +0.0262] over 186 questions (interval excludes zero).
- ml minus base_rate: Brier difference -0.0441, 95% interval [-0.0878, +0.0019] over 186 questions (interval includes zero).
- distill_1_5b minus base_1_5b: Brier difference -0.0107, 95% interval [-0.0166, -0.0052] over 90 questions (interval excludes zero).
- distill_1_5b minus qlora_1_5b: Brier difference +0.0040, 95% interval [-0.0002, +0.0084] over 90 questions (interval includes zero).
- distill_1_5b minus claude_teacher: Brier difference +0.0997, 95% interval [+0.0540, +0.1357] over 90 questions (interval excludes zero).
- distill_1_5b minus base_rate: Brier difference +0.0341, 95% interval [+0.0002, +0.0647] over 90 questions (interval excludes zero).
- distill_1_5b minus ml: Brier difference +0.1019, 95% interval [+0.0287, +0.1527] over 90 questions (interval excludes zero).
- claude_teacher minus base_rate: Brier difference -0.0656, 95% interval [-0.0995, -0.0303] over 90 questions (interval excludes zero).
- claude_teacher minus ml: Brier difference +0.0022, 95% interval [-0.0417, +0.0490] over 90 questions (interval includes zero).
- qlora_1_5b minus base_rate: Brier difference +0.0301, 95% interval [-0.0039, +0.0603] over 90 questions (interval includes zero).
- ml minus base_rate: Brier difference -0.0678, 95% interval [-0.1162, -0.0022] over 90 questions (interval excludes zero).
- distill_1_5b minus base_1_5b: Brier difference -0.0121, 95% interval [-0.0156, -0.0084] over 276 questions (interval excludes zero).
- distill_1_5b minus qlora_1_5b: Brier difference -0.0012, 95% interval [-0.0046, +0.0019] over 276 questions (interval includes zero).
- distill_1_5b minus claude_teacher: Brier difference +0.0563, 95% interval [+0.0352, +0.0766] over 276 questions (interval excludes zero).
- distill_1_5b minus base_rate: Brier difference +0.0184, 95% interval [+0.0055, +0.0321] over 276 questions (interval excludes zero).
- distill_1_5b minus ml: Brier difference +0.0702, 95% interval [+0.0339, +0.1048] over 276 questions (interval excludes zero).
- claude_teacher minus base_rate: Brier difference -0.0379, 95% interval [-0.0590, -0.0158] over 276 questions (interval excludes zero).
- claude_teacher minus ml: Brier difference +0.0139, 95% interval [-0.0166, +0.0433] over 276 questions (interval includes zero).
- qlora_1_5b minus base_rate: Brier difference +0.0196, 95% interval [+0.0069, +0.0332] over 276 questions (interval excludes zero).
- ml minus base_rate: Brier difference -0.0518, 95% interval [-0.0851, -0.0166] over 276 questions (interval excludes zero).

- All probabilities are the Colab scores (4-bit model plus adapter, Platt map fitted on the validation split only). The student was trained on Claude's probabilities for 1,198 training-split questions (soft labels); no GGUF was exported and it is not a live forecaster. The `claude_teacher` arm is Claude Haiku with the live prompt on the same test questions (routing study).
- Test sets: 186 questions (October 2026) and 90 (1 to 15 November 2026); the six questions of a day are correlated, so intervals are day-block bootstrap intervals.
- Mean absolute difference of probabilities to the teacher (Claude `llm_context`, the routing-study answers): student 0.1688, hard-label QLoRA 0.1737, untuned 0.1826 (over 276 test questions).
- The `ml` champion covers 2280 of these questions (backtest rows).

## What this does and does not show

- Electricity only; 276 test questions from about 45 days; intervals are wide.
- One training run, one seed: a different seed could change the ranking of the two tuned models.
- Colab ran transformers 5.22.2, not the pinned version.
- The untuned arms use their own Platt map fitted on validation, so they are not raw model probabilities.

Paid-call cost: US$0.00.
