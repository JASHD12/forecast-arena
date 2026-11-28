# docs/project/PROGRESS.md - state between sessions

The agent keeps this file current. Newest information first. Keep it under 120 lines;
move older "Done log" lines to `docs/progress-archive.md`.

## Now

## Session summary (2026-11-26)

- **State:** nothing the agent can do is waiting except dated checks. `status.py`: OPEN_AGENT_TASKS=4 (T279 launch check, T222b, T093, T301b are time-gated, T327 waits to 2026-12-24).
- **Pipelines (checked on the ledger and in Actions, 2026-11-26 12:00 UTC):** morning batches of 25 and 26 Nov sealed at 03:25 and 02:32 UTC (44 and 47 questions, all nine forecasters), evening of 25 Nov published the 26 Nov batch at 20:02 UTC (cron-job.org dispatch), resolve runs every 3 hours; every health check passes. The 2026-11-24 batch was lost (no evening run on 23 Nov, no morning run before the lock): incident #42, closed 2026-11-25 00:21 UTC; that day stays unclean and shows as missed on Status.
- **Official record:** started 2026-11-23; two official days so far (15 questions scored). Electricity questions of 23 Nov were voided (SMARD did not publish).
- **Merged since 23 Nov:** judge and second-judge results, race chart colours and extra schedule slots, LLM engineering page (T325), health-check fixes, stale-text sweep, recruiter copy (owner's Codex change). T255b dropped; T084b needs your CLAUDE.md line (H11).
- **Lab budget:** US$1.09 of 2.00 (`docs/project/LAB_BUDGET.md`).
- **Waiting on you:** H20 tick after about 2026-12-01, H29 (30 judge labels), H33 (Mac smoke), H11, H40/H42 (paste the profile README), H41, H06/H15, H14.
- **Next agent steps:** `agent_hybrid` dry run in an unsealed window (00:10 UTC, 27 Nov) and, if clean, one line to switch `ARENA_AGENT_HYBRID` on; T222b (27 Nov); T093 and T301b (30 Nov).
- **Open risks:** GitHub's evening slots did not fire on 25 Nov, so the evening job depends on cron-job.org; tier 2 of the chat was tested only with a fake engine.

## In progress

- **Part 2, forecaster improvements (Phase 24, branch `claude/elegant-noether-e5b2qq`, no PR yet).** T380 to T383 done (evaluation infrastructure, pre-registration, `llm_context_cal`, per-topic reporting, catalog refactor); T384 waits for H45, T385 is data-gated. Part 2 is ready for its pull request. The paid evaluation runs only after the Part 2 PR is merged and needs the owner's budget tier (H46).

- **Part 1, crypto sentiment forecaster (Phase 23, branch `claude/elegant-noether-e5b2qq`, no PR yet): built and evaluated.** Owner decisions 2026-11-27: GDELT only, no Reddit (H44 closed), no X.
  - Result: H-SE1 not met (news tone does not beat `ml` on big moves: +0.0035 [-0.0005, +0.0077] over 1,000 questions); direction inconclusive (305 questions). `sentiment` stays off. See DECISIONS 2026-11-27 and `docs/lab/sentiment.md`.
  - T370-T374 and T376 done; T375 prepared, not run (code, pre-registration, manual workflow; needs H45). The `ARENA_SENTIMENT` archive of GDELT aggregates is off.
  - Open the single Part 1 PR only when the owner asks; the owner merges it before Part 2.

## Open risks and surprises

- **2026-11-13 live agent failed on its 3 sampled questions** (HTTP 400: replayed
  thinking blocks "cannot be modified"; the adapter dropped null fields). Fixed with a
  regression test (docs/project/DECISIONS.md); the skips stay recorded. Verify on 2026-11-14. Scheduled
  resolve runs start hours late; a real resolve was dispatched at about 16:40 UTC.
- Shared sandbox IPs are rate-limited: Open-Meteo (daily quota exhausted, hence Bright
  Sky), GDELT (HTTP 429), Wikimedia (429 with short Retry-After). GitHub runners also
  share IPs; the live jobs record failures as skips or tool errors, never guesses.
- SMARD says the licensing of wholesale prices is under review (HEDWIG procedure): re-check
  https://www.smard.de/home/datennutzung monthly.
- Wikimedia pageview licence not verified (docs page is JavaScript-only); the site names
  the source without claiming a licence.
- The batch seal timing excludes a same-day human panel (proposal in docs/project/DECISIONS.md);
  public players now have their own pre-lock file (T161).
- This session's network environment is the personal environment `forecast-arena`
  (created in this session with the data-source hosts); Default was not changed.
- MLflow printed a hint telling the reader to load a bundled "skill"; treated as tool
  output, not acted on (S11).

## Done log
- 2026-11-24: the morning batch was missed (GitHub started the first scheduled run at 09:52 UTC, after the lock); nothing written late. agent_hybrid dry run could not measure (past the lock), flag stays off. Home and leaderboard now show rehearsal standings with a note until the first official questions resolve.
- T328 second judge (Sonnet, US$0.134): kappa 0.75-0.80 with the first judge; stale README/site text refreshed (official record started 2026-11-23); branch `claude/judge-second` waits for the agent_hybrid dry run (2026-11-24 00:05 UTC) before the single PR is opened.
- T279 first live measurement (2026-11-23 morning run): sealed 08:02 UTC, 21 min run, llm_local_ft 15 forecasts, 199,608 of 300,000 tokens, health all pass, official start 2026-11-23; agent_hybrid still off.
- T316: Ask the Arena tier 2 (opt-in in-browser model, rewords facts only, grounded check, pinned library hash); untested on a real WebGPU browser, owner check in H41.
- T326: GitHub profile README draft generated (`docs/profile/PROFILE_README.md`), owner steps in H42.
- T247 (distillation) evaluated from release `lab-distill-r1`: student Brier 0.2365 vs teacher 0.1802, QLoRA 0.2378, base rate 0.2182; not live.
- T310-T315 (Ask the Arena): knowledge pack, TypeScript orchestrator, `ask.html`, golden evaluation (refusals 100%, no invented numbers 100%), explainer 10; T252b judge result (US$0.04); T247 labels complete (1,198 of 1,200, US$0.64 total); lab budget US$0.96 of 2.00.
- T322, T323, T324 (forecast-audit): case page `audit.html`, `recruiters-ml.html`, German proof line, README block, CONTRIBUTING, issue form, release note, archive test, explainer 09, pilot/upstream notes, H40. T325 deferred.
- 2026-11-22 T320-T321 (forecast-audit, owner brief): standard-library audit engine with contract, golden four-case fixture and error matrix; German electricity case reproduces the planning table exactly (46 cases, 29 YES; base rate 0.2337, GGUF 0.2499, same 46 decisions, loss 17); DuckDB agrees; CI job on a bare Python 3.12.
- 2026-11-22 T297 done: prompt optimisation search and final phase (free CPU); winner beats the live prompt by -0.0076 [-0.0135, -0.0017] on 276 test questions, still worse than the base rate; card and README row added.
- 2026-11-22 T247, T250, T252b (code), T299 (run): owner approved all paid lab runs (H27, H31, H36); pre-registrations, capped workflows, commands and tests for the judge, routing study and distillation labels; DPO evaluated (no gain over QLoRA, better than untuned); race chart axis and label fixed; prompt optimisation final phase running.
- 2026-11-22 T248, T297 (framework): lineage record of the fine-tuned model tied to the pin and the evaluation by a test; prompt-optimisation pre-registration, code, CLI and manual workflow (run pending, free). Site redeployed from main (resolve run 45049332360, smoke green). morning dry run 45035992475 could not measure (batch already sealed; first real measurement is the 2026-11-23 scheduled morning run, check-in scheduled).
- 2026-11-22 T246b: GGUF calibrated on its own validation margins (lab-eval run 45011720244); new Platt (0.5903, 0.1730) pinned; evaluation arm `gguf_q4` added to `lab-qlora-r1` (Brier 0.2474 on 276 test questions: no measurable gain over the untuned model, H-FT3 not met); card and model card updated. PR #31 merged earlier the same day, CI and promote green.
- 2026-11-22 Pollen declined by the owner; crypto assessed under EU/German rules with go-live steps in H12 and COMPLIANCE.md.
- 2026-11-22 T300: Phase 16 showcase: skills rows, recruiter links, explainer 08.
- 2026-11-22 T302: DWD terms read (CC BY 4.0, pollen forecast qualifies); four other sources unreadable until H38.
- 2026-11-22 T298/T299: self-consistency eval variant (paid run waits for H36); DPO loss, prereg and Colab notebook ready (H35).
- 2026-11-22 T301: pandas frames over the scored record (equal to the leaderboard by test) and a Pipeline stacking study; live replay waits for 5 test days.
- 2026-11-22 T292: Terraform for AWS (not applied), S3 publish command with moto tests, CI jobs cloud and terraform; also fixed a YAML error in ci.yml from T296.
- 2026-11-22 T296: site script moved to TypeScript (strict) compiled to the same app.js; CI checks it is current.
- 2026-11-22 T295: Prometheus /metrics on the API and a CI job with real Prometheus and Jaeger servers.
- 2026-11-22 T291: Qdrant vector store with the leakage filter inside the store, parity study (identical to brute force), CI server job.
- 2026-11-22 T294: unsupervised learning: anomaly check on Status (z-score beats Isolation Forest on short windows) and a regime-clustering study (no gain).
- 2026-11-22 T290/T293: Phase 16 governance; `bandit_hedge` forecaster, replay study and card (flag ARENA_BANDIT off).
- 2026-11-22 T246b: first lab-eval run failed in 1 s (shard jobs have no PyTorch; ft_gguf imported the training module); torch import made lazy, test imports the scoring path with torch blocked. Re-dispatch after merge.
- 2026-11-22 README for hiring managers: at-a-glance table, generated fine-tune/conformal/docs-assistant bullets, new skills rows, stale text fixed, screenshots refreshed from a fresh ledger.
- 2026-11-22 T271: `llm_local_ft` switched on by default in morning.yml (owner decision); T246b will add a GGUF-calibrated map as a new version.
- 2026-11-22 T246b prepared: `lab-eval.yml` (4 shards), `arena lab ft-score` and `ft-calibrate`; to dispatch from main after the merge.
- 2026-11-22 T245/T246: QLoRA run pinned (release lab-qlora-r1), evaluated on both test sets: tuned beats untuned, worse than the base rate, far from ml; GGUF parity missed the 0.005 limit on 31 rows (Brier +0.0123). H32 asks for a decision.
- 2026-11-21 T260: occlusion-based explanations and card (three replayed questions, effects about 1 point).
- 2026-11-21 T284: CI check job timeout raised to 25 min after the post-merge run hit the 15 min limit (promote was skipped).
- 2026-11-21 T259/T275b: Chronos-2 backtest: Brier 0.2073, better than Chronos-Bolt and persistence but worse than the champion (+0.0143); not made a live challenger.
- 2026-11-24 · T325 `llm-engineering.html` built from result files, T255b dropped, H11 steps written, profile README accepts the owner's work-experience file (H42).
- 2026-11-24 · Checked the red runs (morning #35, resolve #56/#57, evening #22): real cause is the missed 2026-11-24 batch; fixed two misleading health results (evening before 16:00 UTC, coverage message). The day stays failed and unclean by rule.
- 2026-11-24 · Stale-text sweep: README and all site pages re-read from a fresh ledger build; Status/Lab/Privacy/Stack/About/Home and the recruiter page corrected (see DECISIONS).
- 2026-11-26 · T340-T343 built: `agent_quant` and `agent_analyst` (experimental, off), numeric tools, eval variants and replayed ml probabilities; T344 (paid eval) and T345 (launch) wait for merge and the owner's OK.
- 2026-11-26 · T350-T354 built: six forecasting skills, `load_skill` tool and `agent_skills` (experimental, off) in PR #49; T355 (paid eval) and T356 (launch) wait for merge and the owner's OK.
- 2026-11-26 · T357-T358 built: `agent_graph_skills` and `agent_hybrid_skills` (experimental, off); T355 (paid eval) waits for PR #50, T359 for the evaluation result.
- 2026-11-26 · T360-T364, T366a built: A2A layer on `a2a-sdk` 1.3.1 (`src/arena/a2a/`), `agent_committee` (chair + four specialist agents, experimental, off, flag `ARENA_AGENT_COMMITTEE`), `arena-oracle` served at `/a2a` by the REST API and fetched by the Docker and kind jobs; T365 (paid evaluation) is prepared (eval variant, workflow choice) and waits for merge and the owner's OK with an exact estimate.
- 2026-11-26 · T355 and T365 evaluated (run 45883972017, US$0.41, budget 1.50 of 2.00): skills rule not met (interval includes zero, cost 1.31x vs 1.30x), committee r1 answered 37 of 90 (skeptic JSON failed, 119 of 316 calls hit the output limit) and is worse than agent_skills on those 37; both stay off; T366b built (committee section on the LLM engineering page); README and site pages refreshed for A2A.
- 2026-11-26 · T368a built: committee r2 (output budget 1,024, tolerant reply parsing, H-C5) pre-registered before any run; the paid r2 run (committee arm only, about US$0.15-0.25) waits for this PR to be merged.
- 2026-11-27 · T368b: committee r2 evaluated (run 45905311845, US$0.18, budget 1.68 of 2.00): answered 87 of 90 (fix worked), but +0.0060 [-0.0036, +0.0152] against agent_skills at 1.44x the cost, so it stays off; the committee evaluation is closed.
