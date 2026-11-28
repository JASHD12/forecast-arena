# agent_analyst (starts from the ml forecast) and a calibrated llm_context

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-analyst-and-calibration.json`, created 2026-11-28T12:59:38.401898+00:00.

Why companies use it: Starting an LLM from the classical model's forecast and recalibrating a hedging model's probabilities are the two cheapest ways companies try to make an LLM forecaster competitive. (anthropic-evals)

| Variant | Questions | Brier | Log score | ECE | US$ per 1,000 | US$ per 1,000 answered |
|---|---|---|---|---|---|---|
| agent_analyst / November | 90 | 0.1257 | 0.409 | 0.1144 | 0.9755 | 0.9755 |
| llm_context (raw) / November | 90 | 0.1374 | 0.4345 | 0.1124 | 0.4977 | 0.4977 |
| llm_context_cal (map, no tokens) / November | 90 | 0.1287 | 0.4013 | 0.0588 | - | - |
| ml (replayed) / November | 90 | 0.1352 | 0.4376 | 0.1741 | - | - |
| agent (reused run) / November | 90 | 0.1302 | 0.4178 | 0.1009 | - | - |
| base_rate / November | 90 | 0.203 | - | - | - | - |
| llm_context (raw) / October | 186 | 0.1968 | 0.5711 | 0.0697 | 0.554 | 0.554 |
| llm_context_cal (map, no tokens) / October | 186 | 0.1943 | 0.5634 | 0.0609 | - | - |
| ml (replayed) / October | 186 | 0.1814 | 0.5219 | 0.1177 | - | - |
| base_rate / October | 186 | 0.2255 | - | - | - | - |

- agent_analyst minus ml: Brier difference -0.0095, 95% interval [-0.0168, -0.0025] over 90 questions (interval excludes zero).
- agent_analyst minus agent: Brier difference -0.0045, 95% interval [-0.0408, +0.0330] over 90 questions (interval includes zero).
- agent_analyst minus llm_context: Brier difference -0.0117, 95% interval [-0.0503, +0.0284] over 90 questions (interval includes zero).
- llm_context_cal minus llm_context: Brier difference -0.0086, 95% interval [-0.0240, +0.0139] over 90 questions (interval includes zero).
- llm_context_cal minus llm_context: Brier difference -0.0026, 95% interval [-0.0162, +0.0120] over 186 questions (interval includes zero).

- November: run eval-20261128T125938 of llm-eval.yml on power-2026-11a.jsonl (90 questions); October: run eval-20261128T155637 on power-2026-10.jsonl (186 questions). The agent arm is reused from run eval-20261126T195707 (same golden file, hash checked).
- `ml` is the replayed walk-forward probability of the production power model (`evals/golden/ml-probs-*.json`), not the live forecaster. `llm_context_cal` is the raw answers through the fixed map fitted once on lab training questions of 2019 to June 2026; none of the November or October questions is in that training set.
- Versions: agent_analyst `claude-haiku-5-5|prompt-v1-c34fe4efced0|tools-4|out-1024|analyst-r1`; llm_context `claude-haiku-5-5|prompt-v1-b60acd4b5b85|out-1024`.
- Paired differences are Brier(first) minus Brier(second) with day-block 95% intervals on the questions both answered; negative means the first is better.

## What this does and does not show

- Electricity only (the one topic a replay can reproduce), 90 and 186 questions from 15 and 31 days; the six questions of a day are correlated, so intervals are day-block intervals.
- One run, one sample of the model's answers; a repeat could differ. The November set had been used before for other arms (three comparisons here, no multiplicity correction).
- Replayed `ml`, not the live model; weather, Wikipedia, currencies and crypto are judged only on live days.

Paid-call cost: US$0.24.
