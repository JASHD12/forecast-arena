# Pre-registration: monthly retrain rule for the fine-tuned model (`llm_local_ft`)

Registered 2026-11-21, before any retrain code or run (SPEC 17, rule L2). Owner decision of the same day: retrain monthly on the owner's own Mac.

## Rule

1. **Cadence.** Once a month, started by the owner's own scheduler. The job does nothing if the newest day with a known outcome is not at least 28 days
   after the live model's training cut.
2. **Data.** Replayed days only (the leak-free replay builder), never live outcomes (I8). New cut = last replayable day. Train = all days up to
   cut minus 60 days, validation (Platt fit) = the next 30 days, held-out = the final 30 days before the cut.
3. **Comparison.** The candidate and the live model score the same held-out questions with the same prompt and the same calibration procedure.
4. **Promotion.** Promote only if the candidate's Brier on the held-out window is not worse than the live model's (paired day-block interval
   does not exclude the live model being better). Otherwise keep the live model and record "kept" with both numbers.
5. **Never automatic.** A promotion is an uploaded asset plus a pull request that changes `lab/artefacts/llm_local_ft.json`; the owner merges it.
   The new `forecaster_version` differs from the old one; the old version keeps its live record.
6. **No tuning on live questions.** Nothing else is tuned between retrains (I8). The recipe changes only through a new pre-registration.

## Recipe note

The Colab recipe (bitsandbytes 4-bit) is CUDA-only. On Apple Silicon the recipe is an MLX LoRA on a 4-bit base: a different artefact family.
It is accepted for live use only after the smoke run (T281a) meets: fits 16 GB, one run under 6 hours, and its Brier on the frozen
`test_oct` set within 0.005 of the Colab model's (or better). If not, the retrain stays manual on Colab.
