# docs/project/PROGRESS.md - state between sessions

The agent keeps this file current. Newest information first. Keep it under 120 lines;
move older "Done log" lines to `docs/progress-archive.md`.

## Now

## Session summary (2026-11-23)

- **State:** every agent task that does not wait on you, on a date or on a blocked host is done. `status.py` lists only those.
  Merged and deployed: forecast-audit (tool, German electricity case, `audit.html`, recruiter pages), Ask the Arena (tiers 0 and 1,
  optional tier 2), judge result, distillation (labels and Colab evaluation), profile README draft, stale-text refresh.
- **Live (verified on the ledger, 2026-11-23 morning run):** five topics (crypto live), 43 questions, sealed 08:02 UTC (88 minutes before the
  lock), `llm_local_ft` live, 199,608 of 300,000 tokens, all health checks pass, official record started 2026-11-23.
- **Lab budget:** US$0.96 of 2.00 (`docs/project/LAB_BUDGET.md`).
- **Waiting on you:** H41 (test the in-browser model in Chrome/Edge), H42 (paste the profile README), H40 (CV, contact, About text, pilot), H29 (30 judge
  labels), H33 (Mac smoke), H06/H15 (panel, players), H14 (Impressum). Waiting on dates: T222b (2026-11-27), T093 and T301b (2026-11-30).
  Blocked host: T255b (Phoenix docs). T325 is deferred until a role is chosen.
- **Next agent steps:** the `agent_hybrid` launch check (dry run of `morning.yml` with `experimental=true`, scheduled for 2026-11-24 00:05 UTC because today's batch is sealed), then each
  WAIT task when its date passes (T327, the `ml`-first routing evaluation, waits until 2026-12-24). The pre-registration for the `ml`-first routing rule is committed (`lab/prereg/routing-ml-only.md`).
- **Open risks:** tier 2 of the chat was tested only with a fake engine (no real WebGPU here); GitHub starts scheduled runs hours late (H20).

## In progress

Nothing. See the session summary above and `python scripts/status.py`.

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
