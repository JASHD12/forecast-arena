# A committee of specialist agents over A2A against one agent with skills

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-agent-committee.json`, created 2026-11-26T19:57:07.450167+00:00.

Why companies use it: Multi-agent systems and the A2A protocol are how companies split a job between specialised agents; the question is whether the split beats one agent with the same tools. (a2a-protocol)

| Variant | Questions | Brier | Log score | ECE | US$ per 1,000 |
|---|---|---|---|---|---|
| agent_skills / eval | 90 | 0.1279 | 0.4091 | 0.1057 | 1.3928 |
| agent_committee / eval | 37 | 0.147 | 0.4562 | 0.0414 | 1.4162 |
| base_rate / eval | 37 | 0.1908 | - | - | - |
| agent_skills / same items as agent_committee | 37 | 0.1289 | - | - | - |

- agent_committee minus agent_skills: Brier difference +0.0181, 95% interval [+0.0034, +0.0334] over 37 questions (interval excludes zero).

- Run eval-20261126T195707 of llm-eval.yml on power-2026-11a.jsonl (90 questions), replay with the tools a replay can honour; labelled evaluation, never the live record.
- The replay has no news backend and no retriever: the news scout answered 'no evidence available' and the historian gave the base rate only, so this tests a reduced committee.
- Skips per arm: agent_skills none; agent_committee {'error': 53}. Versions: agent_skills `claude-haiku-5-5|prompt-v1-78474be2c501|tools-4|out-1024|quant-r1|skills-r1-d011316a`; agent_committee `claude-haiku-5-5|prompt-a752bbec04d4|committee-r1|members-quant-r1,hist-r1,scout-r1,skeptic-r1|a2a-1.0|sdk-1.3.1|guards-r1|skills-d011316a|out-1024`.
- agent_committee answered 37 of 90 questions; its cost per answered question is 3.44 US$ per 1,000.
- Cost is the run's recorded tokens at the list price of the model, per arm; this result carries the cost of agent_committee.
- Brier of the arms that answered fewer questions is on their answered items only; paired differences use the questions both arms answered (the pair's n).

## What this does and does not show

- Electricity only (the one topic a replay can reproduce), 90 questions from 15 days; the six questions of a day are correlated, so the intervals are day-block intervals.
- One run, one sample of the model's answers; a repeat could differ.
- Weather, Wikipedia, currencies and crypto are judged only on live days.

Paid-call cost: US$0.13.
