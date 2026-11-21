# "Experiments lab": QLoRA fine-tuning plus the industry techniques hiring managers look for

> The plan for Phase 14 (T240 onward), written 2026-11-21 and approved by the owner in chat the same day. All of
> AGENTS.md and CLAUDE.md still apply. Progress is tracked in `docs/project/TASKS.md`; this file is the design.

## 0. Context

- **Why.** The owner wants Werkstudent interviews in Germany (AI engineering, ML/MLOps, data science). The project already
  shows a lot: live forecasters, backtests, MLflow, Evidently, Optuna, SHAP, conformal diagnostics, RAG, LangGraph,
  MCP, dbt, Airflow, Docker and kind. What it does **not** show is any model adaptation of an LLM (no LoRA/QLoRA/SFT/
  distillation), LLM-as-judge, guardrail testing, hybrid retrieval with reranking, cost routing, quantization, ONNX
  serving or shadow deployment. Those are exactly the items that recur in 2025-2026 German job ads and in company
  engineering blogs (research of 2026-11-21: RAG, agents/MCP, evals and LLM-as-judge, fine-tuning with LoRA/QLoRA,
  observability, gateways and routing, LightGBM global and probabilistic forecasting, shadow deployment, ONNX, data
  validation).
- **What.** A clearly separated **Experiments lab**: each technique is a small, pre-registered experiment against the
  existing baselines, run without leakage, with honest results (negative ones included), a model card, and one card on
  a new site page `lab.html`. Nothing here changes the live record unless a later, separate owner decision promotes it
  through the existing versioning and champion/challenger rules.
- **Owner decisions taken (2026-11-21, in chat):**
  - GPU work runs on a **free Colab T4 that the owner starts**. The agent writes the notebook and the exact steps.
  - Up to **about US$2 in total, one-off**, on top of the daily live caps, for paid Claude calls (distillation labels,
    LLM-as-judge). Every paid run is still a single, capped, manual workflow dispatch that the owner approves first.
  - **Full program.**
  - Results go on a new **Lab page** plus model cards, the explainer, the README and the recruiter page.
- **Facts from the code that shape the plan:**
  - The live ledger has only about 172 resolved questions, which is too few to train on. Training data therefore comes
    from **leak-free replay**. `arena.evals.golden.build(domain, first, last, resolve_at)` already rebuilds questions,
    as-of contexts and outcomes for any past day:
    - power from 2018-10 (6 questions a day, about 16,000 rows);
    - markets from 2019 (`markets_domain_from_rates`);
    - attention only partly; weather not faithfully (no MOSMIX history).
  - `LLMContext.user_prompt(q, ctx, asof)` and `prompts.load("system")` (`src/arena/forecasters/llm.py`,
    `src/arena/llm/prompts/`) produce exactly the live prompt.
  - `llm_local` = Qwen2.5-1.5B-Instruct GGUF Q4_K_M via llama-cpp-python (`src/arena/llm/local.py`, pinned revision).
  - The eval harness lives in `src/arena/evals/run.py` (`VARIANTS`, `EvalCaps`, paired day-block intervals). Results
    are `evals/results/*.json` with `kind="evaluation"`.
  - `arena eval run` refuses non-fake runs outside GitHub Actions (S8). The frozen test set is
    `evals/golden/power-2026-10.jsonl` (186 items, Oct 2026).
  - Backtests use `src/arena/backtest/harness.py::walk_forward` (pluggable forecasters, `label="backtest"`, stored in
    `backtests/`, which is git-ignored). Model cards are built by `src/arena/backtest/cards.py` into `docs/models/*.md`.
  - The registry (`src/arena/forecasters/registry.py`) only handles joblib artefacts on the ledger, so LLM adapters
    need their own pinned-artefact record. `ts_bench.py`'s `CHRONOS_REVISION` plus `model_hash` is the precedent.
  - Retrieval (`src/arena/agent/retrieval.py`) is fastembed `bge-small-en-v1.5` with brute-force cosine search.
  - `GuardedLLM`, `BudgetGuard` and `EvalCaps` exist in `src/arena/llm/budget.py`.
  - pandera was rejected once (`docs/project/DECISIONS.md`, about line 508). Read the reason before task T262.

## 1. Lab rules (add to SPEC as a new section 17 "Experiments lab", with a DECISIONS line quoting the owner's approval)

- **L1. Evaluation-only.** Every lab result is `kind="evaluation"` or `label="backtest"`, carries an EVALUATION or
  BACKTEST banner, and never enters a leaderboard, finding or headline (I4). No live forecaster, prompt or threshold
  changes because of a lab result (I8). Promotion to live is a separate owner item, and then goes through a new
  `forecaster_id` or version and the existing weekly rule.
- **L2. Pre-registration.** Before any training or paid run, commit `lab/prereg/<exp>.md` with:
  - the hypothesis;
  - the train, validation and test windows;
  - the metric (Brier on the frozen test set; paired day-block interval vs named baselines);
  - the decision rule, and what counts as a negative result.

  Hash it into the result JSON.
- **L3. Time-based splits, no leakage.**
  - Train: power batch days 2018-12-01 to 2026-06-30.
  - Validation: 2026-07-01 to 2026-09-30, used for early stopping and calibration only.
  - Test: the frozen golden set for October 2026, plus a second frozen set for 2026-11-01 to 2026-11-15. Build it
    before training and commit its hash.
  - Qwen2.5's knowledge cutoff (2024) predates the test windows. Write that into the data card.
- **L4. Reproducible artefacts.** Every dataset, adapter and quantized file has a SHA-256, the base-model revision, the
  code SHA, seeds and package versions in a model card. Large files live as GitHub release assets uploaded by the owner,
  never in git and never on the ledger. Code pins them by URL plus SHA-256 and refuses a mismatch (an `error` skip,
  never a fallback).
- **L5. Cost and safety.**
  - Paid calls only inside GitHub Actions, through `GuardedLLM` with a hard per-run cap.
  - A running total in `docs/project/LAB_BUDGET.md`, computed from the result JSONs, must stay at or below US$2.00.
  - Committing a workflow that sends `ARENA_LLM_API_KEY` for **non-forecast** purposes (labels, judge) is outside
    standing approval 2 in CLAUDE.md. It needs owner item **H27** ticked first.
- **L6. Dependencies.**
  - Lab-only packages go into separate pinned files (`requirements/lab-*.txt`), installed only by lab workflows and
    the CI job that tests lab code with fakes. Colab-only packages (trl, bitsandbytes) are pinned inside the notebook.
  - Look up the current version and licence of each package in official docs first and record them in
    `docs/SOURCES.md` with the date. Add one DECISIONS line per new dependency.
  - `make check` stays network-free. Lab code is unit-tested with tiny fakes (`FakeLLM`, `HashEmbedder`, a 2-layer
    toy model).
- **L7. Honest reporting.** Each experiment has a model or experiment card in `docs/lab/<exp>.md`, generated by code
  from the result JSON, with a "what this does and does not show" block and the ten likely interview questions.

## 2. Phases and tasks (one branch and one PR per task unless noted; `main` is protected; never merge)

Each task lists **Where it runs**:
- **local**: offline CPU in the agent sandbox, using caches;
- **CI**: tests only;
- **Actions**: a manual workflow dispatched from `main` after merge, one at a time;
- **Colab**: the owner.

Each task is ticked only after its "Done when" checks and `make check` pass, plus `make a11y` if it touches the site.

### Phase L0: foundation (do first)

- **T240 Lab charter and governance.**
  - Files:
    - `docs/project/LAB_PLAN.md` (this section);
    - SPEC section 17 (rules L1 to L7);
    - DECISIONS entry "2026-11-21 owner approved the Experiments lab", with the four decisions above;
    - `docs/project/LAB_BUDGET.md` (table: run, date, workflow run id, tokens, US$, running total);
    - HUMAN_TODO items **H26** (Colab runs), **H27** (approve the non-forecast use of the API key in lab workflows),
      **H28** (upload release assets), **H29** (label 30 rationales for judge calibration), each with exact steps.
  - Done when the docs are merged and `status.py` lists the Phase 14 tasks.
- **T241 Lab dataset builder (`src/arena/lab/dataset.py`, CLI `arena lab dataset build`).**
  - Reuse `evals.golden.build` and `LLMContext.user_prompt`, so prompts match live byte for byte.
  - Output JSONL rows: `{id, domain, template, batch_date, asof, system, user, outcome, base_rate}`. The split comes
    from L3 dates.
  - Domains: power (all templates) and markets. Attention and weather are excluded and the data card says why.
  - Stratified subsample option (`--max-rows`, seeded), because a T4 session fits about 6,000 rows of about
    1,100 tokens.
  - Data card `docs/lab/data-card-forecast-sft.md` covers:
    - row counts per split, template and outcome;
    - YES rate;
    - token-length percentiles (counted with the Qwen tokenizer at card-building time; the tokenizer is only needed for
      the card);
    - date ranges, hashes and the leakage argument.
  - Runs **local** (SMARD and ECB caches exist).
  - The gzipped splits (0.8 MB) are committed in `lab/data/forecast-sft/` with their hashes, so the Colab notebook clones the
    repository and needs no upload (changed from the first draft, which used a release asset).
  - Tests:
    - no batch day appears in two splits;
    - test days come after validation days, which come after train days;
    - prompt equality with `LLMContext.user_prompt` on fixture data;
    - deterministic output (same seed gives the same hash).
- **T242 Lab page skeleton and result schema.**
  - `src/arena/lab/results.py`: a pydantic `LabResult` with fields `kind="evaluation"`, `experiment`, `prereg_sha256`,
    `dataset_sha256`, `artefacts`, `metrics`, `paired`, `cost_usd`, `notes`.
  - `site/templates/lab.html` with one card per experiment from `evals/results/lab-*.json`:
    - what it is;
    - why companies use it (one line with a source from `docs/SOURCES.md`);
    - the result with its interval;
    - the cost;
    - links to the card and the code.
  - Add Lab to the nav under "More" and add a `make a11y` check that the page has the EVALUATION banner.
  - Empty state until results exist.
  - Tests: schema round trip; the page renders the banner and never links lab numbers into boards.

### Phase L1: LLM fine-tuning (headline experiment)

- **T243 Pre-registration and frozen test sets.**
  - `lab/prereg/qlora-forecast.md` (hypotheses below).
  - Build and freeze `evals/golden/power-2026-11a.jsonl` (2026-11-01 to 11-15) with `arena eval build`. Commit its hash
    before any training.
  - Hypotheses:
    - **H-FT1**: QLoRA-tuned Qwen2.5-1.5B beats the same base model on Brier on both test sets.
    - **H-FT2**: it does **not** beat the gradient-boosted `ml` model. This is the expected, honest outcome.
    - **H-FT3**: the 4-bit GGUF export loses less than 0.005 Brier against the merged fp16 model.
- **T244 Training code and Colab notebook.**
  - `src/arena/lab/finetune/` contains:
    - `format.py`: chat template; the target is the single token `YES` or `NO` after a fixed answer suffix, with loss on
      the completion only;
    - `train.py`: TRL `SFTTrainer` plus PEFT LoRA (r=16, alpha=32, dropout 0.05, target modules q/k/v/o/gate/up/down),
      bitsandbytes 4-bit NF4 with double quantization, bf16 compute where the GPU supports it (T4: fp16), learning rate
      2e-4, cosine schedule, 1 epoch, max sequence length 1,536, gradient checkpointing, fixed seed;
    - `score.py`: P(YES) = softmax over the `YES` and `NO` logits of the next token, followed by Platt calibration fitted
      on the validation split only.
  - `notebooks/lab/qlora_qwen_forecast.ipynb` is "Run all" only:
    - pins its packages;
    - downloads `lab-data-v1` and checks its SHA-256;
    - trains;
    - writes `adapter/`, `train_log.json` (loss curve, steps, GPU, minutes), `val_scores.jsonl` and
      `run_summary.json`, plus an MLflow file-store run that is zipped;
    - merges the adapter and exports a GGUF Q4_K_M with llama.cpp's converter (pinned commit);
    - prints the SHA-256 values to paste into the H28 step.
  - Training, scoring and formatting are unit-tested on CPU with a tiny randomly initialised Qwen-architecture config
    (no download) so the code path is proven in CI. The notebook itself is not executed in CI.
  - Second run in the same notebook (a flag): **full fine-tuning is not feasible on a T4 for 1.5B**. Document why
    (memory arithmetic). Run a **LoRA without quantization on Qwen2.5-0.5B** as the "precision ablation", so the card can
    compare QLoRA 1.5B, LoRA 0.5B and the base models.
- **T245 Owner runs Colab (H26) and uploads the assets (H28).**
  - Steps in HUMAN_TODO:
    1. Open the notebook link.
    2. Runtime: T4 GPU.
    3. Run all.
    4. Download the `outputs.zip`.
    5. Create GitHub release `lab-qlora-r1` and attach the files.
    6. Paste the printed hashes into the issue or chat.
  - The agent then commits `src/arena/lab/artefacts.py` with the URLs, SHA-256 values and the base-model revision.
- **T246 Evaluation of the fine-tuned model.**
  - New manual workflow `lab-eval.yml`:
    - CPU, no API key;
    - installs `requirements/lab-ft-eval.txt` (transformers, already pinned in `ts.txt`, plus peft and accelerate on
      the CPU torch from `torch.txt`);
    - downloads the pinned assets, checks their hashes, and scores both frozen test sets.
  - Compared, on the same items:
    1. base Qwen2.5-1.5B with the same logit scoring (zero-shot);
    2. QLoRA 1.5B;
    3. LoRA 0.5B;
    4. GGUF Q4 of the best adapter, through llama-cpp-python with `logprobs` (quantization loss);
    5. existing `llm_local` JSON answers (run the existing `llm-eval.yml` with `local=true` once, free, on the same items;
       raise its timeout if needed);
    6. the `ml` champion recipe from a local power backtest over the test windows (`walk_forward`), stored as reference
       rows;
    7. `base_rate`;
    8. existing Claude `llm_context` rows where items overlap (paired only on the overlap, and labelled so).
  - Metrics:
    - reuse `evals/run.py` metrics: Brier, log score, ECE, paired day-block intervals;
    - add CPU latency per question (p50/p95) and artefact size.
  - Output: `evals/results/lab-qlora-r1.json` (`LabResult`), plus generated cards `docs/lab/qlora-forecast.md` and
    `docs/models/llm-local-ft.md`.
  - Done when the result file is committed, the cards are generated, the Lab page shows it, and the budget table
    records US$0.
- **T247 Distillation from Claude (teacher, student).**
  - Pre-register first. H27 must be ticked before committing the workflow.
  - `lab-distill-labels.yml` (manual) sends 1,200 stratified **training-split** prompts to Claude Haiku through
    `GuardedLLM`, with these caps:
    - at most 1,300 requests;
    - at most 2.2M tokens;
    - estimate about US$0.35 at the list price recorded in `docs/SOURCES.md`; re-check the price first.
  - It stores `{id, probability, rationale}` as release asset `lab-distill-v1` (owner uploads, H28) and commits only
    hashes and usage.
  - The notebook gains a second recipe: soft-label SFT. Train the student on the teacher probability (Brier-style loss
    on the YES/NO logits) and, as a variant, also on the rationale text (rationale distillation, as in Netflix's
    post-training work).
  - Evaluate with T246's workflow. Compare student vs teacher vs hard-label QLoRA on Brier, cost per 1,000 questions
    and latency.
  - This is the "cost-quality trade-off" story for interviews.
- **T248 Adapter registry and lineage.**
  - `src/arena/lab/registry.py` (or an extension of `forecasters/registry.py` with an `ExternalArtefact` kind) records
    base model and revision, dataset hash, prereg hash, code SHA, package versions, metrics and release URL.
  - The loader refuses a hash mismatch.
  - MLflow: the Colab run's file store is summarised into `docs/lab/runs/qlora-r1.json` (params, metrics, artefact
    hashes).
  - The weekly MLflow logging is unchanged.
- **T249 (owner-gated, optional) Shadow run of the fine-tuned model.**
  - Only if T246 shows `llm_local_ft` is not worse than `llm_local`, and the owner ticks a new item.
  - Run it in the morning job on the same daily sample as a **shadow** forecaster: write records to a separate
    `shadow/` tree on the ledger with `kind="shadow_forecast"`, excluded from every board, scored only on the Lab page
    (canary/shadow pattern from Uber's deployment-safety post).
  - Needs a SPEC 8 information-set table entry and ledger schema support with tests. Otherwise skip and note it as a
    proposal.

### Phase L2: LLM engineering techniques

- **T250 Cost routing and cascades (zero cost).**
  - `src/arena/lab/routing.py`: route each golden item to the cheapest forecaster first, in the order `ml`/`base_rate`,
    then `llm_local`, then Claude. Escalate when the cheap forecaster is uncertain (`|p-0.5| < delta`) or two cheap
    models disagree.
  - Compute the cost-vs-Brier Pareto curve **offline from stored eval and backtest rows** (no new calls).
  - Choose delta on the validation window and report on the test window.
  - Card: "router saves X% of paid calls at Y Brier".
  - Also report a semantic-cache hit-rate estimate (cosine of `bge-small` prompt embeddings over 0.97, day by day). The
    expected answer is "near 0, because contexts change daily": an honest negative.
- **T251 Hybrid retrieval: BM25 plus dense, RRF fusion, cross-encoder rerank.**
  - `src/arena/agent/retrieval.py` gains:
    - `BM25Index`, implemented in numpy with no new package;
    - `hybrid_search` using Reciprocal Rank Fusion (k=60);
    - an optional reranker via fastembed's ONNX cross-encoder (check that the current fastembed supports
      `TextCrossEncoder`, pick a small MS-MARCO MiniLM model, record it in SOURCES).
  - Retrieval eval set `evals/golden/retrieval-v1.jsonl` from resolved replay questions. Relevance labels are
    deterministic: same template and entity within ±30 days and a similar threshold; graded 2/1/0.
  - Metrics recall@5, MRR and nDCG@5 for each arm (dense, BM25, hybrid, hybrid+rerank), plus latency.
  - The live agent keeps the current retriever (I8). Switching is a later prompt or version change with an owner item.
- **T252 Grounding check and LLM-as-judge.**
  1. A deterministic **numeric grounding** metric: every number in a rationale must appear, within rounding, in the
     prompt context or the question. Run it over all stored live rationales and eval rows (free) and report the
     ungrounded-number rate per forecaster.
  2. **LLM-as-judge** with a rubric (Anthropic's guidance: detailed rubric, reasoning before score, constrained JSON
     output) grading 100 stored rationales on data use, correct direction and hedging. One capped Actions run of about
     US$0.10, gated on H27.
  3. **Judge calibration**: the owner labels 30 rationales via a CSV (H29). Report Cohen's kappa between the judge and
     the owner, and judge self-consistency over 2 runs.
  - The same judge runs with local Qwen for a free comparison.
- **T253 Guardrails and red-team suite.**
  - `src/arena/llm/guards.py`:
    - input guard for tool and news text (instruction-pattern heuristics; strip URLs or code blocks; length cap);
    - output guard (schema, probability range, grounding from T252);
    - a PII scrub for headlines (email and phone regex), in line with S7.
  - `tests/redteam/cases.yaml` holds about 40 attack cases (instruction in a headline, fake tool result, JSON breakout,
    role-play), run with `FakeLLM` in `make check` for the harness logic.
  - A free `lab-eval.yml` mode runs them against `llm_local` and reports the attack success rate with the guards off
    and on.
  - The live agent gets the guards only through a new prompt or harness version and an owner item. Otherwise the result
    is report-only.
- **T254 Docs RAG assistant with citations ("Ask the project").**
  - `arena lab ask "question"`: retrieves chunks of `docs/` (SPEC, methods, explainers) using the T251 hybrid retriever
    and answers with the local model or the FakeLLM. Answers must cite chunk ids. If no chunk scores above a threshold,
    it says "not in the docs".
  - Eval: 30 hand-written Q&A pairs in `evals/golden/docs-qa-v1.jsonl`, measured on citation precision, answer
    faithfulness (T252 grounding plus the judge) and refusal correctness.
  - Expose it as an extra MCP tool in `mcp_server.py` (local only). This is the "internal knowledge assistant" pattern
    companies build.
- **T255 Prompt and model observability export.**
  - Extend `llm/otlp.py` with GenAI semantic-convention attributes for the lab runs (model, adapter hash, tokens,
    latency).
  - Add a CI job that loads the exported traces into **Arize Phoenix** (a single container; check the current image
    and licence) through OTLP and asserts the span count, then stops it.
  - Store one screenshot in `docs/img/` for the Lab card.
  - If the image is too heavy for CI, document it and keep it as a `make smoke-phoenix` target.

### Phase L3: ML and forecasting techniques (all backtest-only, CPU, local)

- **T256 Calibration methods compared.**
  - Platt vs isotonic vs beta calibration (implement beta calibration with scikit-learn logistic regression on log
    features; no new package).
  - Applied to the power champion's out-of-fold scores in a walk-forward backtest.
  - Report Brier, ECE and reliability curves.
  - If isotonic wins with an interval that excludes 0, propose a new `power-gbq-r2` challenger through the weekly rule.
    Never swap the live champion directly.
- **T257 Conformal prediction coverage study.**
  - Turn `ops/explain.py::cqr_margin` into a walk-forward study: 80% and 90% CQR intervals for the daily mean price, with
    empirical coverage by month and slice and interval width.
  - Optionally (owner item) show the 80% interval on electricity question pages as "experimental", with coverage tracked
    live.
- **T258 Global LightGBM model (Zalando/MLForecast pattern).**
  - One global quantile model across all power statistics, with a statistic id feature, lags and calendar features,
    against the per-statistic champion. Same walk-forward and Optuna budget.
  - Report Brier, pinball loss and training time. If it wins, it enters the weekly challenger list as family `glgbm`.
- **T259 Time-series foundation models, zero-shot.**
  - Add Chronos-2 (via the chronos-forecasting package, if the current version supports it; check first) and/or
    TimesFM 2.5 (check the licence and CPU feasibility) to `ts_bench.py`, next to the existing Chronos-Bolt.
  - Report Brier and latency in the power backtest card `docs/models/power-ts.md`.
- **T260 Per-forecast explanations (explainable AI).**
  - For the power champion, compute the top-3 feature contributions per forecast (SHAP TreeExplainer for the LightGBM
    family; permutation-based local attribution for HGB) in the backtest, and show 3 example question pages in the Lab
    card.
  - Live display only through an owner item, because it changes the forecast meta and needs a version change.

### Phase L4: MLOps and data

- **T261 ONNX export and serving parity.**
  - Export the power champion and the attention LightGBM to ONNX (skl2onnx / onnxmltools; check versions and support
    for HistGradientBoosting quantile loss; if unsupported, export the LightGBM challenger only and say so).
  - Parity test: probabilities equal within 1e-6 on 500 backtest rows.
  - Latency benchmark against joblib.
  - Add `POST /predict/power` to `api/app.py` (FastAPI, ONNX Runtime), exercised by the existing Docker and kind CI
    jobs.
  - Record the ONNX file hash in the registry metadata.
- **T262 Data contracts and validation.**
  - Read the earlier pandera rejection. If its reason still holds, write the contracts as pydantic models plus a YAML
    of expectations (freshness, ranges, completeness, uniqueness) checked by a small in-house runner. Otherwise use
    pandera with a DECISIONS line.
  - Apply them to the lab datasets (T241) and to the daily snapshots. A failure is a recorded health warning, never a
    silent drop.
  - Data-quality section on the Status page.
- **T263 Shadow and canary for the weekly challenger (Uber pattern).**
  - The weekly job already scores challengers on 28 past days. Add a 7-day **shadow period**: the selected challenger
    forecasts live questions daily into `shadow/` (same mechanism as T249), and promotion requires the shadow window to
    be not worse.
  - Needs the T249 ledger support and an owner item, because it changes the promotion rule. Otherwise report-only, as a
    proposal.

### Phase L5: showcase (last)

- **T264 Explainer and interview pack.**
  - `docs/explainers/06-experiments-lab.md`: how each experiment works, why, what was rejected, honest limits, ten
    interview questions with answers.
  - `docs/interview/numbers.md`: lab numbers generated by `scripts/interview_numbers.py`.
  - README: a "What I experimented with" table generated by `scripts/readme_sections.py`.
  - Recruiter page: a role-to-experiment map:
    - AI engineering: QLoRA, distillation, judge, guardrails, hybrid RAG, routing;
    - ML/MLOps: ONNX, shadow, registry, calibration, global model;
    - data science: conformal, foundation models, explanations.
- **T265 Final sweep.**
  - `make check`, `make a11y` (layout audit at 3 widths includes `lab.html`), a site build from a fresh ledger clone,
    and the budget table at or below US$2.
  - PROGRESS session summary.
  - After merge, dispatch `resolve.yml` once to redeploy.

### Suggested order and parallelism

1. T240, then T241 and T242.
2. T243 and T244. The owner then runs T245.
3. T246, then T247 and T248.
4. Phase L2, L3 and L4 tasks are independent of each other after T242. Do them in this order:
   1. T250 (free, quick win);
   2. T251, T256, T257;
   3. T252, T253 (need H27 and H29);
   4. T258, T259, T261, T262, T254, T255, T260.
5. Last: T249 and T263 (owner-gated), then T264 and T265.
6. While the owner's Colab run is pending, work on Phase L2, L3 and L4. Never wait idle.

## 3. Critical files

| Area | Files |
|---|---|
| New | `src/arena/lab/{dataset,results,routing,registry}.py`, `src/arena/lab/finetune/{format,train,score}.py`, `src/arena/llm/guards.py`, `notebooks/lab/qlora_qwen_forecast.ipynb`, `site/templates/lab.html`, `.github/workflows/{lab-eval,lab-distill-labels}.yml`, `requirements/lab-*.txt`, `lab/prereg/*.md`, `docs/lab/*.md`, `docs/project/{LAB_PLAN,LAB_BUDGET}.md`, `evals/golden/{power-2026-11a,retrieval-v1,docs-qa-v1}.jsonl`, `tests/unit/test_lab_*.py`, `tests/redteam/cases.yaml` |
| Extended | `src/arena/evals/run.py` (new variants and metrics), `src/arena/agent/retrieval.py`, `src/arena/backtest/{power,cards}.py`, `src/arena/forecasters/ts_bench.py`, `src/arena/api/app.py`, `src/arena/mcp_server.py`, `src/arena/llm/otlp.py`, `src/arena/site/build.py` and `base.html` (nav), `scripts/{interview_numbers,readme_sections}.py`, SPEC section 17, DECISIONS, SOURCES, HUMAN_TODO, TASKS, PROGRESS |
| Reuse, do not rewrite | `evals/golden.build`, `LLMContext.user_prompt`, `prompts.load`/`fingerprint`, `GuardedLLM`/`BudgetGuard`, `scoring/stats.py` (day-block bootstrap, Diebold-Mariano), `backtest/harness.walk_forward`, `BacktestStore`, `ops/explain.cqr_margin`, `ml_power_lgbm.train_lgbm` (Optuna), `retrieval.FastEmbedder`/`HashEmbedder`, `llm/local.py` (`llama_backend`) |

## 4. Verification

- **Per task:** unit tests with fakes, `make check` (network-free), `make a11y` for site work, and CI green on the PR.
- **Experiments:**
  - the result JSON validates against `LabResult`;
  - the prereg hash matches the committed prereg;
  - dataset and artefact hashes match their cards;
  - paired intervals are computed only on identical item sets;
  - the Lab page shows the banner and the interval;
  - no lab number appears on leaderboard, findings or home standings (a test greps the built boards for lab ids).
- **Leakage tests:**
  - no test-window day in the train or validation files;
  - the retrieval eval excludes questions resolved after the query's as-of time;
  - distillation labels come from the training split only.
- **Cost:** `LAB_BUDGET.md` is summed from the result JSONs by a script in `make check` and must be at or below 2.00.
  Each paid workflow has hard caps and runs only after the owner approves the dispatch.
- **End to end:** after merge, one `resolve.yml` dispatch, then a check that `lab.html` is deployed and the smoke step is
  green. Ask the owner to look.

## 5. Honest expectations to write into the cards before results exist

- QLoRA 1.5B will probably beat its own base model and probably **not** beat the gradient-boosted model on electricity.
  That is a strong, explainable interview result about when fine-tuning a small LLM is the wrong tool.
- Routing is the most likely clear win: it saves paid calls at almost unchanged Brier.
- The semantic cache is likely useless here, because contexts change daily. Reported as a negative.
- Hybrid RAG with rerank usually beats dense-only on keyword-heavy queries; the size of the gain is unknown until
  measured.


---

# Part 2: "Everything in the lab goes live": Phase 15, deploy the lab techniques as real forecasters and monitors

> Tasks T270 onward are Phase 15 in `docs/project/TASKS.md`. All of AGENTS.md and CLAUDE.md apply.

## 0. Owner decisions of 2026-11-21 (in chat, recorded in DECISIONS)

1. **The fine-tuned model runs live as a forecaster**, whatever its backtest result is (a loser is also a result). It is frozen,
   pre-registered, labelled "experimental", and never changes because of live results (I8).
2. **Daily LLM token cap raised from 150,000 to 300,000** (live usage is about 130,000; SPEC 9.4's own default is 400,000).
3. **All lab techniques also run live**: cascade router, agent with hybrid retrieval and guards, weekly challengers (global LightGBM,
   Chronos-2), live monitoring on Status (grounding rate, data contracts, experimental conformal interval).
4. The first draft's rule "never live" (SPEC 17 L1) and the shadow-forecasting tasks T249/T263 are **superseded**: a new forecaster
   is simply a forecaster with its own id; no shadow tree is needed.

Why it was separate before: integrity rules I4 (live and backtest never mix) and I8 (no tuning on the live record). Both are kept, by a
different mechanism: **backtest first, then freeze the version and go live**, exactly as `ml` did. The model is trained only on replayed
days up to 2026-06-30, so the live record has not shaped it.

## 1. Integrity design for new live forecasters (applies to every item below)

- **New `forecaster_id` and a `forecaster_version` that changes with the artefact** (SPEC 8.5): artefact SHA-256, Platt coefficients,
  prompt fingerprint and retriever version are in the version string; history of other forecasters is untouched.
- **Written before the lock, same sample, same contract** as the other LLM forecasters (SPEC 8.4 daily sample, `not_sampled`/
  `model_missing`/`error` skips with reasons, never a default probability, I6).
- **Boards:** `COMMON_GROUP` (base_rate, ml, llm_plain, llm_context, agent) and the ensemble members stay unchanged, so the headline
  common-set board and the ensemble do not move. New forecasters appear on the "all questions" and per-topic boards with an
  "experimental, since <first day>" chip and are compared only on questions they answered (existing coverage logic); the Methods
  information-set table (SPEC 8) gets one row each.
- **Official record:** the official start is 2026-11-23 (H24). A forecaster that goes live later is allowed; it simply has fewer days.
- **No post-hoc edits:** a pre-registered expectation sits next to each (`lab/prereg/*.md`); any change after launch is a new id.
- **Cost:** local model costs nothing; Claude-based additions fit the 300,000 cap (measured, see T279).

## 2. Tasks (Phase 15; order matters; each ticked only after its checks and `make check`, plus `make a11y` for site work)

- **T270 Governance for going live.** SPEC: amend section 17 L1 (lab results stay evaluations; a lab technique may also run live as an
  experimental forecaster under section 1 above), add information-set rows for `llm_local_ft`, `llm_router`, `agent_hybrid` to the SPEC 8
  table, note the 300,000 cap in 9.4. DECISIONS entry quoting the four owner decisions; TASKS Phase 15; mark T249 and T263 superseded;
  HUMAN_TODO H32 (confirm the Colab outputs so the model can go live). Done when docs are in the PR and `status.py` lists Phase 15.
- **T271 `llm_local_ft`, the fine-tuned model as a live forecaster** (needs the Colab artefacts: H26, H28; code and tests can be written now).
  - `src/arena/forecasters/llm_ft.py`: `LLMLocalFT` (`forecaster_id = "llm_local_ft"`), same prompt as `llm_context`
    (`LLMContext.user_prompt` + `system`), scores with llama.cpp: tokenise the chat-templated prompt, `eval`, read the last-position logits,
    margin = logit(YES) - logit(NO) (ids checked to be single tokens), P = Platt(a, b) from the Colab validation fit, clipped to [0.01, 0.99].
  - `src/arena/lab/artefacts.py` pins release URL, SHA-256 (refuse a mismatch: `model_missing` skip with the reason), Platt (a, b), base
    revision, adapter hash. Version string: `qwen2.5-1.5b-qlora-r1|gguf-<sha8>|platt|prompt-v1-<fingerprint>`; meta carries margin and a, b.
  - Wiring: `build_forecasters` appends it after `llm_local` when `settings.llm_local_ft` (`ARENA_LLM_LOCAL_FT=1`); shares the daily LLM
    sample; run budget raised (about 2,300-token prompts; measure first, T279).
  - Workflows: `morning.yml` downloads the release asset with `actions/cache` keyed by the SHA-256, verifies it, reuses the llama-cpp
    install of `llm_local`. Look up the current `actions/cache` major version first (AGENTS section 7).
  - Parity check (CI-free workflow or notebook cell): GGUF Q4 margins vs the fp16 merged model on 20 test rows within a stated tolerance.
  - Tests: fake llama backend (margins to probabilities, hash mismatch skip, single-token check, time-limit skip); version string changes
    with the artefact.
- **T272 Site and boards for the new forecasters.** Names and colours (`site/titles.py`, `charts.SERIES_SLOTS`), forecaster pages,
  "experimental, since <day>" chip, Methods information-set rows, Lab page section "Live experimental forecasters" linking to their
  boards (live numbers come from the ledger, never typed). A test checks that none of them is in `COMMON_GROUP` or the ensemble.
- **T273 `llm_router`, the cascade forecaster.**
  - `src/arena/forecasters/router.py`, `needs_peers = True` like the ensemble: for each sampled question it chooses among forecasts the
    peers already wrote: answer with the cheap pair (mean of `ml` and `llm_local_ft`) when both are decisive (`|p-0.5| >= delta`) and agree
    (`|ml - ft| <= gamma`), otherwise take `llm_context`. It records `escalated` and `paid_calls_avoided` in meta, so the live saving is
    measured on the shared sample without extra paid calls.
  - `delta`, `gamma` are chosen on the validation window only and frozen in the version string. Needs Claude test rows (H31, one paid
    `llm-eval` run, about US$0.15) and the T246 scores, so it is written after them; until then it is not registered.
  - Listed after the forecasters it reads (like the ensemble). Tests with fixed peer forecasts.
- **T274 `agent_hybrid`, the agent with hybrid retrieval and guards.**
  - A retriever wrapper around `PastQuestions.search_hybrid` (BM25 + dense + RRF + cross-encoder rerank) with the same leakage rule;
    `AgentForecaster(... retriever=hybrid)` under the id `agent_hybrid` next to `agent` (side-by-side comparison, same sample).
  - Harness-level guards: `llm/guards.sanitize` on news headlines, Wikipedia summaries and every tool output before the model sees them,
    flags written to the trace span attributes; the guard version is part of the forecaster version.
  - Reranker weights (about 80 MB) cached by `actions/cache` like the fastembed model.
  - Needs the 300,000 cap: change `ARENA_LLM_MAX_TOKENS_PER_DAY` (check the exact setting name in `config.py` and `morning.yml`) and record the
    measured daily usage after one week in PROGRESS.
  - Tests: leakage property test (never returns a question resolved after the forecast time), guard flags in spans, version string.
- **T275 Weekly challengers (`glgbm`, `chronos2`).**
  - `forecasters/ml_power_global.py`: one global LightGBM quantile model over all power statistics (statistic id feature, lags, calendar),
    same walk-forward and Optuna budget as `ml_power_lgbm.py`; `ts_bench.py` wrapper for Chronos-2 turning predicted quantiles into
    P(statistic > T) like `ml_power`.
  - Registered as candidate families in `ops/weekly.py`, scored by the existing 28-day rule (promote only if not worse), so each can become
    the live `ml` power champion by the written rule, never by hand. Weekly workflow installs the extra requirement files.
  - Backtest cards `docs/models/power-global.md`, update `power-ts.md`. Tests on fixtures; no network in `make check`.
- **T276 Live monitoring on Status and question pages.**
  - Rationale grounding: `lab/grounding.py` over the last 7 days of stored rationales, a table on Status (not-in-prompt share per forecaster).
  - Data contracts (T262): pydantic models plus a small expectations runner (freshness, ranges, completeness, uniqueness) as health checks in
    `ops/health.py`; failures are recorded health warnings (existing incident flow), never silent drops. Read the earlier pandera rejection
    first (`DECISIONS.md` about line 508).
  - Experimental 80% conformal interval for the electricity mean-price questions: the weekly job stores the CQR margin in the registry
    metadata (`ops/explain.cqr_margin`), `ml` writes the interval into the forecast meta (probability unchanged), the question page shows it
    as "experimental" and Status tracks empirical coverage from resolved questions.
- **T277 Serving parity (ONNX) in the deployed container.** Export the LightGBM power challenger (and the champion if `skl2onnx` supports
  HistGradientBoosting quantile loss; check, otherwise say so) to ONNX, parity within 1e-6 on 500 backtest rows, `POST /predict/power` in
  `api/app.py` using ONNX Runtime, exercised by the existing Docker and kind CI jobs; the hash goes into the registry metadata.
- **T278 Colab results and evaluation (unchanged from Phase 14): T245/T246 and, after them, T247 (distillation, H27), T248, T252b (judge,
  H27/H29), T254 (docs assistant), T255 (trace export), T250 (replaced by T273)**; distilled student, if it beats the QLoRA model on the
  validation window, replaces the artefact in T271 as a new version, never silently.
- **T279 Launch checks (before turning each flag on in the workflows).** Dispatch `morning.yml` once from `main` with `dry_run=true` and the
  new flags to measure runner minutes per question and token use (the manifest reports usage); set the run budget and the cap from the
  measurement; dry runs write nothing to the ledger (existing behaviour). Then enable the flags one at a time (`ARENA_LLM_LOCAL_FT`,
  `ARENA_AGENT_HYBRID`, router) on separate days so the first-day problems are attributable; each launch is an owner-visible PROGRESS line.
- **T280 Showcase and final sweep.** Update explainer 06 (live section: what runs live, version strings, expectations written before the
  first live day), README table, recruiter roles (live forecasters named), interview numbers generated from the ledger, `make check`,
  `make a11y`, redeploy with one `resolve.yml` dispatch.

## 3. Owner actions (exact steps go to `docs/project/HUMAN_TODO.md`)

- **H26, H28** (still the critical path): run the Colab notebook on a free T4 and upload `outputs.zip` as a GitHub release.
- **H32** reply "go" after the agent shows the evaluation of the fine-tuned model (it goes live whatever the result, but you see it first).
- **H27** (paid distillation and judge runs, within US$2.00) and **H31** (one paid test-set run, about US$0.15) as before; **H29** label
  30 rationales; **H30** no longer needed.

## 4. Order and parallelism

T270 first. Then T274, T275, T276, T277 (independent, need no owner input). T271 code and T272 can be written now; T271 goes live after
H26/H28. T273 after T271 and H31. T279 gates every flag. T280 last. While the Colab run is pending, never wait idle.

## 5. Risks to watch

- Runner CPU time for 2,300-token prompts (measure in T279); the morning job must still seal before the 09:30 UTC lock.
- 1 GB model download per run: cache by hash; a cache miss must not break the lock-critical run (skip with `model_missing`, never block).
- Daily token cap: measure after enabling `agent_hybrid`; if the cap is hit forecasts become `budget_exhausted` skips (visible, I6).
- Adding forecasters changes board layouts: the layout audit and a11y checks run in T272 and T280.
