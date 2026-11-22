# QLoRA fine-tune of Qwen2.5-1.5B on replayed power questions

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-qlora-r1.json`, created 2026-11-22T01:40:43Z.

Why companies use it: Parameter-efficient fine-tuning of a small open model is the standard way companies adapt an LLM to a narrow task; the comparison with a classical model is the point.

| Variant | Questions | Brier | Log score | ECE |
|---|---|---|---|---|
| base_1_5b / test_oct | 186 | 0.249 | 0.6912 | 0.0817 |
| qlora_1_5b / test_oct | 186 | 0.24 | 0.6729 | 0.0902 |
| base_0_5b / test_oct | 186 | 0.251 | 0.6952 | 0.1291 |
| lora_0_5b / test_oct | 186 | 0.2308 | 0.653 | 0.0962 |
| base_rate / test_oct | 186 | 0.2255 | 0.6406 | 0.0851 |
| ml / test_oct | 186 | 0.1814 | 0.5219 | 0.1177 |
| base_1_5b / test_nov | 90 | 0.2477 | 0.6886 | 0.0491 |
| qlora_1_5b / test_nov | 90 | 0.233 | 0.6586 | 0.1175 |
| base_0_5b / test_nov | 90 | 0.2513 | 0.6958 | 0.1719 |
| lora_0_5b / test_nov | 90 | 0.2262 | 0.6439 | 0.1017 |
| base_rate / test_nov | 90 | 0.203 | 0.588 | 0.0564 |
| ml / test_nov | 90 | 0.1352 | 0.4376 | 0.1741 |
| base_1_5b / test_all | 276 | 0.2486 | 0.6904 | 0.0585 |
| qlora_1_5b / test_all | 276 | 0.2378 | 0.6683 | 0.0687 |
| base_0_5b / test_all | 276 | 0.2511 | 0.6954 | 0.143 |
| lora_0_5b / test_all | 276 | 0.2293 | 0.65 | 0.0875 |
| base_rate / test_all | 276 | 0.2182 | 0.6235 | 0.0591 |
| ml / test_all | 276 | 0.1663 | 0.4944 | 0.0673 |

- qlora_1_5b minus base_1_5b: Brier difference -0.0090, 95% interval [-0.0148, -0.0028] over 186 questions (interval excludes zero).
- qlora_1_5b minus base_rate: Brier difference +0.0145, 95% interval [+0.0021, +0.0262] over 186 questions (interval excludes zero).
- qlora_1_5b minus ml: Brier difference +0.0586, 95% interval [+0.0121, +0.1001] over 186 questions (interval excludes zero).
- lora_0_5b minus base_0_5b: Brier difference -0.0202, 95% interval [-0.0294, -0.0110] over 186 questions (interval excludes zero).
- lora_0_5b minus base_rate: Brier difference +0.0053, 95% interval [-0.0132, +0.0230] over 186 questions (interval includes zero).
- lora_0_5b minus qlora_1_5b: Brier difference -0.0092, 95% interval [-0.0176, -0.0012] over 186 questions (interval excludes zero).
- ml minus base_rate: Brier difference -0.0441, 95% interval [-0.0878, +0.0019] over 186 questions (interval includes zero).
- qlora_1_5b minus base_1_5b: Brier difference -0.0147, 95% interval [-0.0221, -0.0079] over 90 questions (interval excludes zero).
- qlora_1_5b minus base_rate: Brier difference +0.0301, 95% interval [-0.0039, +0.0603] over 90 questions (interval includes zero).
- qlora_1_5b minus ml: Brier difference +0.0979, 95% interval [+0.0244, +0.1469] over 90 questions (interval excludes zero).
- lora_0_5b minus base_0_5b: Brier difference -0.0252, 95% interval [-0.0371, -0.0140] over 90 questions (interval excludes zero).
- lora_0_5b minus base_rate: Brier difference +0.0232, 95% interval [-0.0176, +0.0592] over 90 questions (interval includes zero).
- lora_0_5b minus qlora_1_5b: Brier difference -0.0068, 95% interval [-0.0161, +0.0012] over 90 questions (interval includes zero).
- ml minus base_rate: Brier difference -0.0678, 95% interval [-0.1162, -0.0022] over 90 questions (interval excludes zero).
- qlora_1_5b minus base_1_5b: Brier difference -0.0109, 95% interval [-0.0154, -0.0062] over 276 questions (interval excludes zero).
- qlora_1_5b minus base_rate: Brier difference +0.0196, 95% interval [+0.0069, +0.0332] over 276 questions (interval excludes zero).
- qlora_1_5b minus ml: Brier difference +0.0714, 95% interval [+0.0354, +0.1061] over 276 questions (interval excludes zero).
- lora_0_5b minus base_0_5b: Brier difference -0.0218, 95% interval [-0.0289, -0.0144] over 276 questions (interval excludes zero).
- lora_0_5b minus base_rate: Brier difference +0.0111, 95% interval [-0.0055, +0.0288] over 276 questions (interval includes zero).
- lora_0_5b minus qlora_1_5b: Brier difference -0.0085, 95% interval [-0.0146, -0.0022] over 276 questions (interval excludes zero).
- ml minus base_rate: Brier difference -0.0518, 95% interval [-0.0851, -0.0166] over 276 questions (interval excludes zero).

- Probabilities are the Colab scores (4-bit model plus adapter, Platt map fitted on the validation split only); the live model is the Q4_K_M GGUF of the merged adapter.
- Test sets: 186 questions (October 2026) and 90 (1 to 15 November 2026); the six questions of a day are correlated, so intervals are day-block bootstrap intervals.
- The `ml` champion covers 2280 of these questions (backtest rows).
- GGUF parity on 31 test rows: mean absolute margin difference 0.0881, Brier 0.2131 (GGUF) against 0.2008 (Colab), loss +0.0123; 29.6 s per question on CPU.

## What this does and does not show

- Electricity only; 276 test questions from about 45 days; intervals are wide.
- One training run, one seed: a different seed could change the ranking of the two tuned models.
- Colab ran transformers 4.57.6, not the pinned version.
- The untuned arms use their own Platt map fitted on validation, so they are not raw model probabilities.

Paid-call cost: US$0.00.
