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

## What runs live (Phase 15)

The owner decided on 2026-11-21 that lab techniques are also real forecasters, not only evaluations. They go live the way `ml` did:
backtest first, then freeze the version, then write forecasts before the lock like every other forecaster.

| Forecaster | What it is | Switch |
|---|---|---|
| `llm_local_ft` | the QLoRA-tuned Qwen, scored by one forward pass (YES/NO logit margin, Platt calibrated); frozen artefact pinned by SHA-256 | `ARENA_LLM_LOCAL_FT`, on by default since 2026-11-22 (variable `0` switches off) |
| `agent_hybrid` | the LangGraph agent with hybrid retrieval (BM25 + dense + RRF + cross-encoder) and harness guards | `ARENA_AGENT_HYBRID`, off until a launch dry run |
| `llm_router` | cascade over peers: cheap pair when decisive and in agreement, otherwise `llm_context`; registered only when its thresholds file exists | file `lab/artefacts/llm_router.json` |
| `glgbm` | global LightGBM challenger, promoted only by the weekly 28-day rule | weekly job |

- **Not in the headline.** None of them is in the common set or the ensemble, so the headline board and ensemble do not move. They carry an
  "experimental, since <day>" label and are compared only on questions they answered.
- **Never changed by live results (I8).** A new model is a new version string. Retraining is a pre-registered monthly check on the owner's own
  machine (`lab/prereg/qlora-retrain.md`); a candidate replaces the live model only if it is not worse on a held-out window, through a pull
  request the owner merges.
- **Monitoring.** Status shows the grounding rate, the data contracts and the coverage of an experimental 80% conformal band for electricity prices.
- **Serving parity.** The LightGBM power models export to ONNX and `POST /predict/power` answers with ONNX Runtime (probabilities within 1e-4).
  The live HistGradientBoosting champion does not convert (skl2onnx 1.20 cannot build its quantile-loss trees), so it stays on joblib.

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

- **The fine-tune ran once (card `docs/lab/qlora-r1.md`).** It beat its own untuned base model, as predicted, and it does **not** beat the
  gradient-boosted `ml` model, as predicted. Two results were not predicted and are the honest headline: the tuned 1.5B model is also worse
  than the plain base rate (an interval that excludes zero), and the smaller 0.5B LoRA model scored slightly better than the 1.5B QLoRA model.
  One run and one seed, so the ranking of the two tuned models is not settled. The 4-bit GGUF that would run live missed the pre-registered
  parity limit on a 31-question subset, so it is not live yet (owner decision H32).
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

## Update of 2026-11-22: what the later experiments showed

All numbers below are from the committed result files in `evals/results/` and the cards in `docs/lab/`; the shared test sets are the
276 frozen power questions (46 days), Brier score, lower is better.

- **Quantisation cost most of the fine-tuning gain.** The tuned 4-bit model scored 0.2378; the Q4_K_M GGUF that actually runs
  live scores 0.2474, the same as the untuned model (0.2486). The pre-registered limit for the export loss (0.005) was missed
  (+0.0076), and the GGUF's logit margins correlate only 0.54 with the Colab scores. Lesson: evaluate the artefact you deploy,
  not the one you trained.
- **DPO on top of QLoRA changed nothing measurable** (0.2363 against 0.2378, interval includes zero), but it beat the untuned
  model like QLoRA did. Both tuned models remain worse than the base rate (0.2182) and far from the gradient-boosted model (0.1663).
- **Prompt optimisation is a small, real gain that does not rescue the small model.** A pre-registered search over eight prompts,
  chosen on 48 validation questions, beat the live prompt by about 0.008 Brier on the test sets (interval excludes zero) but still
  lands at 0.2556. Solved examples made things worse.
- **Claude is clearly better than the base rate on these questions** (0.1802, interval excludes zero) and not distinguishable from
  the gradient-boosted model. The pre-registered cascade (cheap pair first) saved nothing because the open model is never confident;
  a simpler `ml`-first cascade looks promising (about three quarters of paid calls avoided at a better Brier) but it was picked from
  a grid after the fact, so it is a hypothesis for new days, not a result.
- **Self-consistency (five samples averaged) did not help** (-0.002, interval includes zero) and cost 5.2 times as much.

### More questions an interviewer may ask

11. **Why is your deployed model worse than the one you evaluated in Colab?**
    The export to 4-bit GGUF changed the numbers: the quantised merged model gives different logits. I measured it on all 276 test
    questions, refitted the calibration on the GGUF's own validation margins, and published the loss instead of hiding it.
12. **Why did you refuse to build the router after the study?**
    I wrote the build condition (at least 30% of paid calls saved) before the paid answers existed; the pre-registered rule saved 0%.
    The better-looking rule is a hypothesis from a post-hoc grid, so the honest next step is a new pre-registration, not a build.
13. **When is an LLM judge trustworthy?**
    Only as far as it agrees with a human on the same items. I froze 100 rationales, hid the forecaster name, and have 30 human labels
    pending to report weighted kappa; my first run also showed the usual failure (answers cut off by an output cap), which I fixed
    and recorded instead of dropping the run.
