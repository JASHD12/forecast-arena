# 06 - The Experiments lab: fine-tuning and other production techniques

What the lab is, how an experiment is run so that the result can be trusted, what has been done so far,
and what was rejected. Code: `src/arena/lab/` (dataset, finetune, retrieval_eval, grounding, redteam,
calibration_study, results), `src/arena/llm/guards.py`, `src/arena/agent/retrieval.py` (hybrid search),
`notebooks/lab/qlora_qwen_forecast.ipynb`. Design: `docs/project/LAB_PLAN.md`; rules: SPEC section 17.

## How it works

1. **A lab, not a feature.** Each experiment tries one technique that companies use in production against the
   baselines the project already has, on questions the technique never saw. Every result is an *evaluation*
   (SPEC 17, L1): it carries that label, appears only on the Lab page, never enters a leaderboard or a finding,
   and changes no live forecaster. Promoting something live is a separate owner decision with a new version.
2. **Pre-registered.** Before training or any paid run, `lab/prereg/<experiment>.md` is committed with the
   hypothesis, the data windows, the metric and the decision rule, including what counts as a negative result.
3. **No leakage by construction.** Training rows are rebuilt by replaying the production question, context and
   resolution code for past days (`arena.lab.dataset`). The input is the exact live prompt. Splits are by batch
   day: train (2018-12 to 2026-06), validation (2026-07 to 09), two frozen test windows (October and the first half of
   November 2026). The test files are committed with their hashes before any training.
4. **The fine-tuning experiment (`qlora-forecast`).** Qwen2.5-1.5B-Instruct is loaded in 4 bit (NF4, double
   quantization), a LoRA adapter (r=16, all attention and MLP projections) is trained on 2,000 replayed questions, and the
   model answers with one token: the logits of `YES` and `NO` at the start of the answer give P(YES). Training is a binary
   cross-entropy on the logit difference, which is supervised fine-tuning of that one token. A Platt map fitted on the
   validation split calibrates it. A plain LoRA on the 0.5B model is the precision ablation. Full fine-tuning is documented
   as not feasible on a 16 GB T4 (about 18 GB for weights, gradients and Adam states of a 1.5B model). The GPU run is a
   Colab notebook the owner starts; the code path is unit-tested on CPU with a tiny random model.
5. **Other experiments, finished and run offline:**
   - *Hybrid retrieval* (BM25 + dense vectors fused with reciprocal rank fusion, plus a cross-encoder reranker) on a
     frozen set of 2,004 replayed questions and 186 graded queries: nDCG@5 0.37 dense, 0.34 BM25, 0.35 hybrid, 0.56 hybrid
     with rerank; BM25 has the best first-hit rank (MRR 0.80).
   - *Numeric grounding*: how many numbers quoted in stored live rationales are not literally in the prompt.
   - *Guardrails and a red-team suite*: 61 synthetic cases; 35 of 41 attacks flagged, the 6 evasions (paraphrase, spacing,
     French, base64) missed, none of 20 benign texts flagged.
   - *Calibration methods* on the champion's backtest probabilities: re-calibration lowers the expected calibration error
     (0.070 to 0.055) but no Brier difference excludes zero.
6. **Cost is capped.** All paid calls of the lab together stay under US$2.00 and each is a manual, capped workflow run.
   Nothing paid has been run yet.

## Why it was built this way

- **To show judgement, not a stack of logos.** Each technique has a measured result next to a baseline, and negative
  results are published. A hiring manager can see how a decision was made, not only that a library was installed.
- **Replay instead of waiting.** The live ledger has a few hundred resolved questions; replaying the production code
  gives about 16,000 power questions with real as-of contexts, so training and testing are possible now.
- **A small in-house training loop** instead of TRL: the target is a single token, so the loop is about 100 lines, runs on CPU
  in unit tests, and does not depend on a fast-moving trainer API.
- **Report-only guards.** The live agent keeps its defences (data labelling, harness limits); the guards are measured first.

## What was rejected

- Training on the live ledger (too few rows, and it would let live results shape models: integrity rule I8).
- Fine-tuning a bigger model, or full fine-tuning: does not fit the free GPU.
- Classifying "derived" numbers in the grounding check: with hundreds of numbers in a context almost any value is a
  difference of two of them by chance. The class was dropped; an LLM judge is the right tool for arithmetic.
- A semantic cache and routing claims before the data exists: routing needs paid-model answers on all test items.

## Honest limits

- **The fine-tune has not run yet.** The notebook, code and pre-registration are ready; the result needs a Colab run.
  The expected outcome, written down in advance, is that the tuned model beats its own base model and does not beat the
  gradient-boosted model on electricity.
- Electricity only (one market, replayed outcomes resolve against current data). Test sets are small (186 and 90 questions)
  and the six questions of a day are correlated, so intervals are day-block bootstrap intervals and wide.
- The retrieval grades come from question metadata, not from whether retrieval improves a forecast.
- The guards were refined once on the same red-team set, so their detection rate is optimistic; regex cannot catch paraphrases.

## Ten interview questions

1. **Why fine-tune a 1.5B model for a forecasting benchmark?**
   To measure what adaptation buys on a task with a clear score, and what it costs. The honest prior is that it helps
   the small model and still loses to gradient boosting on tabular price history. Writing that down before the run is the point.
2. **What is QLoRA?**
   The base weights are stored in 4-bit NF4 with double quantization and frozen; small low-rank adapter matrices (here
   r=16) are trained in higher precision. It fits a 1.5B model on a 16 GB T4, where full fine-tuning would need about 18 GB for
   weights, gradients and optimizer states alone.
3. **How do you avoid leakage?**
   Splits by batch day (train before validation before test), contexts rebuilt by the as-of store, test files frozen and hashed
   before training, hyper-parameters fixed in the pre-registration, and a base model whose data ends before every window.
4. **Why a single YES/NO token instead of generating JSON?**
   The loss is then an ordinary binary cross-entropy on two logits, scoring is the same softmax, there is no parsing
   failure, and it is cheap. The cost is losing the rationale text.
5. **Why not use TRL or Unsloth?**
   For a one-token target the loop is short, testable on CPU and independent of trainer API changes. For a generation task
   with a chat format I would use TRL.
6. **What would make you believe the fine-tune is better than the base model?**
   The paired day-block 95% interval of the Brier difference lies entirely below zero on the pooled frozen test days. Anything
   else is reported as "no difference shown".
7. **Why does hybrid retrieval with a reranker help here?**
   Dense vectors blur numbers ("above 246" and "above 316" look alike); BM25 matches exact tokens; fusion keeps both signals and a
   cross-encoder re-reads the top candidates jointly. Rerank costs about 370 ms against 50 ms.
8. **What does the grounding check show and not show?**
   It shows how much of what a model quotes is not literally in its prompt; it cannot tell a legitimate calculation from
   an invention, so it is an upper bound and the judge step is needed.
9. **How good are the guards?**
   They flag 35 of 41 synthetic attacks and none of 20 benign texts, but I tuned them once on that same set and the evasions
   (paraphrase, spacing, other languages) all pass. They are one layer; harness limits and data labelling are the others.
10. **What would you do with a bigger budget?**
    Run the 6,000-row training file for more than one epoch, add a preference-tuning step, distil from the paid model with the
    budget the owner approved, route questions between cheap and paid models by uncertainty, and put a held-out live period behind
    every claim.
