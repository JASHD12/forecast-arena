# Data card: forecast SFT rows (power)

**EVALUATION / EXPERIMENT DATA, not the live record.** Rebuilt by replaying the
production question, context and resolution code for past batch days (SPEC 17,
rule L3). Prompts are the exact live `llm_context` prompts.

| Split | Window | Rows | YES rate | Days | SHA-256 |
|---|---|---|---|---|---|
| test_nov | 2026-11-01 to 2026-11-15 | 90 | 0.4889 | 15 | `b45e6a5440f9a185...` |
| test_oct | 2026-10-01 to 2026-10-31 | 186 | 0.4194 | 31 | `f120884a109778ea...` |
| train | 2018-12-01 to 2026-06-30 | 6000 | 0.4433 | 2591 | `63d387c583ecdaaf...` |
| val | 2026-07-01 to 2026-09-30 | 552 | 0.5018 | 92 | `ffb1d23a2240f4e0...` |

Leakage argument: windows are ordered train < validation < test and never share a
batch day (checked in code); every context was built by the as-of store as it would
have been at 05:30 UTC of the batch day; the base model (Qwen2.5) has a training
cutoff in 2024, before every window. The training split is a seeded,
template-proportional subsample (seed 0).

Limits: power only (attention contexts need live per-article API calls, weather has
no forecast history); the replay resolves against current SMARD values, so later
data revisions can show in outcomes; one German market.
