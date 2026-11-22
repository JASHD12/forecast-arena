# DPO preference tuning of Qwen2.5-1.5B on replayed power questions

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-dpo-r1.json`, created 2026-11-22T20:06:52Z.

Why companies use it: Preference tuning (DPO) is the standard follow-up to supervised fine-tuning for aligning a model with outcomes; comparing it with plain fine-tuning and a classical model shows what the extra step buys.

| Variant | Questions | Brier | Log score | ECE |
|---|---|---|---|---|
| base_1_5b / test_oct | 186 | 0.249 | 0.6912 | 0.0817 |
| dpo_1_5b / test_oct | 186 | 0.2383 | 0.6692 | 0.0832 |
| qlora_1_5b / test_oct | 186 | 0.24 | 0.6729 | 0.0902 |
| base_rate / test_oct | 186 | 0.2255 | 0.6406 | 0.0851 |
| ml / test_oct | 186 | 0.1814 | 0.5219 | 0.1177 |
| base_1_5b / test_nov | 90 | 0.2477 | 0.6886 | 0.0491 |
| dpo_1_5b / test_nov | 90 | 0.2321 | 0.6564 | 0.1075 |
| qlora_1_5b / test_nov | 90 | 0.233 | 0.6586 | 0.1175 |
| base_rate / test_nov | 90 | 0.203 | 0.588 | 0.0564 |
| ml / test_nov | 90 | 0.1352 | 0.4376 | 0.1741 |
| base_1_5b / test_all | 276 | 0.2486 | 0.6904 | 0.0585 |
| dpo_1_5b / test_all | 276 | 0.2363 | 0.665 | 0.0971 |
| qlora_1_5b / test_all | 276 | 0.2378 | 0.6683 | 0.0687 |
| base_rate / test_all | 276 | 0.2182 | 0.6235 | 0.0591 |
| ml / test_all | 276 | 0.1663 | 0.4944 | 0.0673 |

- dpo_1_5b minus base_1_5b: Brier difference -0.0107, 95% interval [-0.0161, -0.0043] over 186 questions (interval excludes zero).
- dpo_1_5b minus qlora_1_5b: Brier difference -0.0017, 95% interval [-0.0037, +0.0007] over 186 questions (interval includes zero).
- dpo_1_5b minus base_rate: Brier difference +0.0128, 95% interval [+0.0008, +0.0244] over 186 questions (interval excludes zero).
- dpo_1_5b minus ml: Brier difference +0.0569, 95% interval [+0.0110, +0.0981] over 186 questions (interval excludes zero).
- qlora_1_5b minus base_rate: Brier difference +0.0145, 95% interval [+0.0021, +0.0262] over 186 questions (interval excludes zero).
- ml minus base_rate: Brier difference -0.0441, 95% interval [-0.0878, +0.0019] over 186 questions (interval includes zero).
- dpo_1_5b minus base_1_5b: Brier difference -0.0157, 95% interval [-0.0244, -0.0074] over 90 questions (interval excludes zero).
- dpo_1_5b minus qlora_1_5b: Brier difference -0.0010, 95% interval [-0.0035, +0.0023] over 90 questions (interval includes zero).
- dpo_1_5b minus base_rate: Brier difference +0.0291, 95% interval [-0.0037, +0.0580] over 90 questions (interval includes zero).
- dpo_1_5b minus ml: Brier difference +0.0969, 95% interval [+0.0245, +0.1455] over 90 questions (interval excludes zero).
- qlora_1_5b minus base_rate: Brier difference +0.0301, 95% interval [-0.0039, +0.0603] over 90 questions (interval includes zero).
- ml minus base_rate: Brier difference -0.0678, 95% interval [-0.1162, -0.0022] over 90 questions (interval excludes zero).
- dpo_1_5b minus base_1_5b: Brier difference -0.0123, 95% interval [-0.0168, -0.0075] over 276 questions (interval excludes zero).
- dpo_1_5b minus qlora_1_5b: Brier difference -0.0015, 95% interval [-0.0032, +0.0005] over 276 questions (interval includes zero).
- dpo_1_5b minus base_rate: Brier difference +0.0181, 95% interval [+0.0054, +0.0311] over 276 questions (interval excludes zero).
- dpo_1_5b minus ml: Brier difference +0.0700, 95% interval [+0.0344, +0.1040] over 276 questions (interval excludes zero).
- qlora_1_5b minus base_rate: Brier difference +0.0196, 95% interval [+0.0069, +0.0332] over 276 questions (interval excludes zero).
- ml minus base_rate: Brier difference -0.0518, 95% interval [-0.0851, -0.0166] over 276 questions (interval excludes zero).

- All probabilities are the Colab scores (4-bit model plus adapter, Platt map fitted on the validation split only). No GGUF was exported for this run (the optional export cell failed on a notebook bug, fixed since), so hypothesis H-DPO3 (export loss) is not tested, and the DPO model is not a live forecaster.
- Test sets: 186 questions (October 2026) and 90 (1 to 15 November 2026); the six questions of a day are correlated, so intervals are day-block bootstrap intervals.
- The `ml` champion covers 2280 of these questions (backtest rows).

## What this does and does not show

- Electricity only; 276 test questions from about 45 days; intervals are wide.
- One training run, one seed: a different seed could change the ranking of the two tuned models.
- Colab ran transformers 5.22.2, not the pinned version.
- The untuned arms use their own Platt map fitted on validation, so they are not raw model probabilities.

Paid-call cost: US$0.00.
