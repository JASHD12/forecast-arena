# Pre-registration: QLoRA fine-tune of a small open model on forecasting questions

Experiment id: `qlora-forecast`. Registered 2026-11-21, before any training run (SPEC 17, rule L2).

## Question

Does supervised fine-tuning of a small open LLM (Qwen2.5-1.5B-Instruct, 4-bit QLoRA) on past, replayed
electricity-price questions make it a better forecaster than the same model without tuning, and does it come
close to the gradient-boosted model that is live as `ml`?

## Data (rule L3)

Rows are the exact live `llm_context` prompts with the outcome as target (`lab/data/forecast-sft/`, data card
`docs/lab/data-card-forecast-sft.md`). Plain-byte SHA-256 of each split:

| Split | Window (batch days) | Rows | SHA-256 |
|---|---|---|---|
| train | 2018-12-01 to 2026-06-30 | 6000 | `63d387c583ecdaaf61d1df1a9158e576ab0341f274638411e2fd857923266f7f` |
| val | 2026-07-01 to 2026-09-30 | 552 | `ffb1d23a2240f4e0de6209775406062d79c6022ebf669eb20a7229aa0a880ee5` |
| test_oct | 2026-10-01 to 2026-10-31 | 186 | `f120884a109778ea0be0674f8649a50548f2668417fadd7a6ce61401ed03c4f8` |
| test_nov | 2026-11-01 to 2026-11-15 | 90 | `b45e6a5440f9a1857e01abd82c6a6520054f994bfa261c2b2e8a2fb3a75d5eae` |

The two test windows are frozen now. The same days exist as eval-harness golden files
(`evals/golden/power-2026-10.jsonl`, sha256 `29939ca9268558fc6e153e3859fa57924536d00ed5530a83808d26a8bdcf8194`; `evals/golden/power-2026-11a.jsonl`,
sha256 `fd31d14b6c5123b30e1c95c18063b28dd41718414af7826d1de02da48801ceac`) so the existing eval results can be paired item by item.
The test days are never used for training, early stopping, calibration or any choice below.

## Models and recipe (fixed here; one training run per recipe, no tuning on test)

| Variant | Base | Method |
|---|---|---|
| `qlora_1_5b` | Qwen2.5-1.5B-Instruct | 4-bit NF4 with double quantization, LoRA r=16, alpha=32, dropout 0.05, all attention and MLP projections |
| `lora_0_5b` | Qwen2.5-0.5B-Instruct | LoRA r=16 on fp16 base (precision ablation) |
| `base_1_5b`, `base_0_5b` | same bases | no training; same scoring |

Training: 1 epoch on a seeded, template-proportional subsample of 2,000 rows of the train file (the live prompts are about
2,300 tokens long, so a free T4 trains about 2,000 rows in roughly an hour; the 6,000-row file stays available for a larger
run), learning rate 2e-4 with cosine schedule and 3% warm-up, effective batch 16, sequence length at most 2,560 tokens
(longer rows are dropped and counted; the longest validation prompt is 2,325), seed 0, fp16 mixed precision. Full fine-tuning of a 1.5B model does not fit a
16 GB T4 (weights, gradients and Adam states are about 12 bytes per parameter, 18 GB before activations), so it is not run.

Scoring: P(YES) is the softmax over the next-token logits of `YES` and `NO` (single tokens in the Qwen tokenizer, checked in
code) at the start of the assistant answer, then a Platt map fitted on the validation split only (all 552 rows).

## Metrics and decision rules

Primary metric: Brier score on the pooled test items (test_oct and test_nov, 276 questions); each window is also reported
alone. Intervals: paired day-block bootstrap (2,000 resamples, fixed seed) from `arena.scoring.stats`, on identical item sets.

- **H-FT1**: `qlora_1_5b` has a lower Brier than `base_1_5b` on the pooled test items. Supported only if the paired 95% interval of
  (qlora minus base) lies entirely below zero.
- **H-FT2** (expected outcome): `qlora_1_5b` does **not** beat the live gradient-boosted `ml` recipe (replayed with
  `walk_forward` on the same days). Supported if the paired interval of (qlora minus ml) lies entirely above zero; if it includes
  zero the result is reported as "no difference shown"; if below zero it is reported as a surprise and checked for leakage first.
- **H-FT3**: the Q4_K_M GGUF export of the best adapter loses less than 0.005 Brier against the merged fp16 model on test_oct.
- Also reported, without a hypothesis: `lora_0_5b`, the existing `llm_local` JSON answers on the same items, `base_rate`, the
  existing Claude `llm_context` rows where items overlap, CPU latency of the GGUF, artefact sizes, training minutes.

## What counts as a negative result

Any outcome other than the one stated is reported exactly as it came out, on the Lab page and in the card. No second training run,
different learning rate, other seed or other split is run after seeing a test result (rule I8). If training diverges (loss not
below the starting loss after the run) that is reported as a failed run and the notebook is fixed and re-run once, with the
failure and the fix recorded.
