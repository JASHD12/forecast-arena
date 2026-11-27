# The committee, version r2 (output budget and reply parsing fixed), against one agent with skills

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-agent-committee-r2.json`, created 2026-11-26T22:49:57.477434+00:00.

Why companies use it: Multi-agent systems and the A2A protocol are how companies split a job between specialised agents; this is the same question as the first run after fixing the defect it exposed. (a2a-protocol)

| Variant | Questions | Brier | Log score | ECE | US$ per 1,000 |
|---|---|---|---|---|---|
| agent_skills / eval | 90 | 0.1279 | 0.4091 | 0.1057 | 1.3928 |
| agent_committee / eval | 87 | 0.1351 | 0.4328 | 0.0953 | 2.0098 |
| base_rate / eval | 87 | 0.2043 | - | - | - |
| agent_skills / same items as agent_committee | 87 | 0.1291 | - | - | - |

- agent_committee minus agent_skills: Brier difference +0.0060, 95% interval [-0.0036, +0.0152] over 87 questions (interval includes zero).

- The agent_skills arm is reused from run eval-20261126T195707 (same golden file).
- Run eval-20261126T224957 of llm-eval.yml on power-2026-11a.jsonl (90 questions), replay with the tools a replay can honour; labelled evaluation, never the live record.
- r2 changes only the output budget and the parsing of the scout's and skeptic's replies (pre-registered before the run). The agent_skills arm is the one of run 45883972017, reused on the same golden file. The replay has no news backend and no retriever, so this still tests a reduced committee.
- Skips per arm: agent_skills none; agent_committee {'error': 1, 'parse_failure': 2}. Versions: agent_skills `claude-haiku-5-5|prompt-v1-78474be2c501|tools-4|out-1024|quant-r1|skills-r1-d011316a`; agent_committee `claude-haiku-5-5|prompt-a752bbec04d4|committee-r2|members-quant-r1,hist-r1,scout-r2,skeptic-r2|a2a-1.0|sdk-1.3.1|guards-r1|skills-d011316a|out-1024`.
- agent_committee answered 87 of 90 questions; its cost per answered question is 2.08 US$ per 1,000.
- Cost is the run's recorded tokens at the list price of the model, per arm; this result carries the cost of agent_committee.
- Brier of the arms that answered fewer questions is on their answered items only; paired differences use the questions both arms answered (the pair's n).

## What this does and does not show

- Electricity only (the one topic a replay can reproduce), 90 questions from 15 days; the six questions of a day are correlated, so the intervals are day-block intervals.
- One run, one sample of the model's answers; a repeat could differ.
- Weather, Wikipedia, currencies and crypto are judged only on live days.

Paid-call cost: US$0.18.
