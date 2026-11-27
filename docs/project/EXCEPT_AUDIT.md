# Audit of the broad `except Exception` clauses (T383, 2026-11-27)

The plan asked to keep the clauses that turn a failure into a recorded skip (I6) and to narrow the rest. All 29 clauses in `src/arena`
were read. **None is silent and none substitutes a number**: each records a skip, a warning, an error field or an empty value, at a boundary
where the exception types are open-ended (a model library, a network client, a trainer). Narrowing them would trade a visible, recorded
failure for a job that crashes on an exception type nobody listed, so none was narrowed; the ones that matter are covered by tests.

| Where | What the failure becomes | Test |
|---|---|---|
| `ops/jobs.py` `_run_forecaster` (and its `version()` call) | an `error` skip with the reason and `forecaster_version` None | `test_jobs.py`, `test_failure_boundaries.py` |
| `ops/jobs.py` prepare / context / question generation / resolve / revision check | a run warning; the question or step is skipped, the others go on | `test_jobs.py` |
| `ops/wiring.py` model loads (`ml`, local, fine-tuned) | a `model_missing` skip with the reason | `test_llm_local.py`, `test_live_ml.py` |
| `ops/weekly.py` training, current-model load, evaluation, refit, drift report, explainability | a recorded decision with `error` set; the weekly job continues | `test_weekly_failures.py` |
| `agent/forecaster.py`, `agent/committee.py` peers | no peer value for the tool (never a guessed one) | `test_failure_boundaries.py`, `test_agent_committee.py` |
| `llm/tracing.py`, `llm/budget.py` | the span or usage is recorded, then the exception is re-raised | `test_tracing.py`, `test_budget.py` |
| `llm/local.py`, `a2a/client.py`, `a2a/server.py` | a typed `LLMError` / `CallResult` failure, never a result | `test_llm_local.py`, `test_a2a_*.py` |
| `domains/attention.py` person lookup | all candidates excluded and a skip message (the conservative reading, S12) | `test_attention*.py` |
| `api/app.py` DuckDB query | an HTTP error response | `test_api*.py` |
| `sources/smoke.py`, `sources/smard.py` probe | a reported failure or an `error` field, never a job failure | `test_smard*.py` |

New clauses need a line here and a test that the failure is recorded.
