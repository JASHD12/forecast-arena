# 08 - Production skills added in Phase 16: what each is, why it is here, what it showed

Added after the owner showed a chart of skills in 2026 AI-engineer job postings. Each item is a real, tested part of the project with a
measured or CI-verified result, and several results are negative: that is deliberate. Design: `docs/project/DECISIONS.md` (2026-11-22).

## What was added

| Skill | Where | What it showed |
|---|---|---|
| Vector database | `agent/vectorstore.py` (Qdrant), CI job `vectordb` | identical nDCG/MRR to brute force on 143 queries; the forecast-time rule is a filter inside the store |
| Cloud as code | `infra/aws/*.tf`, `cloud/s3.py`, CI jobs `terraform` and `cloud` | validated, not deployed (no account); S3 upload tested with boto3 against moto |
| Observability | `api/metrics.py`, `scripts/smoke_observability.sh`, CI job `observability` | Prometheus scrapes `/metrics`, Jaeger stores the OTLP spans, real servers in CI |
| TypeScript | `site_ts/app.ts` to `static/app.js` | strict, no `any`, compiled output checked in CI; browser tests unchanged |
| Online learning | `forecasters/bandit.py`, `lab/bandit_study.py` | Hedge beats the equal-weight mean on the live record, not `ml` alone |
| Unsupervised learning | `ops/anomaly.py`, `lab/regimes.py` | a plain robust z-score beats an Isolation Forest on short windows; k-means regimes do not help |
| pandas and Pipelines | `analytics/frames.py`, `lab/stacking_study.py` | DataFrame views equal the leaderboard by test; stacking replay waits for 5 days |
| LLM techniques | `forecasters/selfconsistency.py`, DPO notebook | self-consistency is an evaluation variant (paid run waits for the owner); DPO is pre-registered for the owner's Colab run |

## Why it was built this way

- **A skill with a measured result, not a logo.** The bandit, the anomaly detectors and the regimes each have a comparison against a simple
  baseline, and the simple baseline often wins; the cards say so.
- **Servers only in CI.** Qdrant, Prometheus and Jaeger run as containers in CI jobs; `make check` stays offline.
- **No money, no accounts.** AWS is code that is validated but never applied (S1, S2).
- **One source of truth.** The pandas views are proved equal to `scoring.leaderboard`; the TypeScript output is proved equal to its source by CI.

## What was rejected

- A MinIO container for the S3 tests: the image is no longer on Docker Hub; moto's S3 implementation is used.
- Switching the live agent to Qdrant: identical results, but a new service in the lock-critical run for no gain.
- A bundler for 350 lines of TypeScript.
- Reinforcement learning with an environment: a forecasting benchmark has delayed feedback, not actions with consequences; expert advice is the honest form.

## Honest limits

- Terraform arguments were not checked against the provider documentation (the registry host is blocked here); `terraform validate` in CI is the check.
- The bandit and stacking replays use only a few live days.
- The Isolation Forest was fitted on 27 points per window; with long histories it may do better.
- New open-data topics (T302) are waiting: DWD pollen qualifies, four other sources need their hosts allowed (H38); crypto waits for H12.

## Ten questions an interviewer may ask

1. Why Qdrant if brute force is identical? The store enforces the leakage rule itself and scales with an index; at 2,000 documents there is no speed gain and the result file says so.
2. How do you prevent leakage in retrieval? `resolved_ts < asof` is part of every Qdrant query; a unit test checks it.
3. Why not deploy to AWS? No account and no spending are allowed here; the code is validated in CI and the budget alarm is part of it.
4. Why is the S3 test not against real S3? moto implements the API boto3 calls; a real bucket needs credentials.
5. Why did the z-score beat the Isolation Forest? 27 points are too few for a forest to separate a single extreme day; a median/MAD rule is robust at that size.
6. What does Hedge do? It keeps weights per topic proportional to `exp(-eta * cumulative loss)`; regret to the best expert is bounded.
7. Is Hedge reinforcement learning? It is the expert-advice/bandit setting: feedback is delayed and the learner's choice does not change the environment.
8. Why standard bounded labels on metrics? Route templates, not ids, so Prometheus cardinality stays bounded.
9. Why TypeScript for 350 lines? Types on the game state and DOM lookups catch missing elements at compile time; the compiled file stays a single self-hosted script.
10. How would DPO differ from your QLoRA run? Same data and budget; for one answer token the DPO loss reduces to a margin loss against the untuned model's margins, and the pre-registered expectation is the same negative result.
