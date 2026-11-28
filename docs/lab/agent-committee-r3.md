# agent_committee r3: working repairs, topic guidance for the chair, a skeptic that sees the data

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-agent-committee-r3.json`, created 2026-11-28T16:26:58.770253+00:00.

Why companies use it: Multi-agent systems and the A2A protocol are how companies split a job between specialised agents; this is the re-test after the defects found in r2. (a2a-protocol)

| Variant | Questions | Brier | Log score | ECE | US$ per 1,000 | US$ per 1,000 answered |
|---|---|---|---|---|---|---|
| agent_skills / eval | 90 | 0.1245 | 0.4003 | 0.0692 | 1.3671 | 1.3671 |
| agent_committee / eval | 66 | 0.1391 | 0.4345 | 0.0827 | 2.3347 | 3.1837 |
| base_rate / eval | 66 | 0.1833 | - | - | - | - |
| agent_skills / same items as agent_committee | 66 | 0.1344 | - | - | - | - |

- agent_committee minus agent_skills: Brier difference +0.0047, 95% interval [-0.0077, +0.0190] over 66 questions (interval includes zero).

- Run eval-20261128T162658 of llm-eval.yml on power-2026-11a.jsonl (90 questions), replay with the tools a replay can honour; labelled evaluation, never the live record.
- r3 carries the failed reply in the chair's repair, cites members in key_factors, gives the chair the topic skill text and the skeptic the stored data. The replay still has no news backend and no retriever (a reduced committee), and the replayed ml probabilities were not passed to the arms.
- Skips per arm: agent_skills none; agent_committee {'budget_exhausted': 12, 'error': 12}. Versions: agent_skills `claude-haiku-5-5|prompt-v1-03d70e91e0e5|tools-4|out-1024|quant-r2|skills-r2-9fd4d88f`; agent_committee `claude-haiku-5-5|prompt-3b248ce29015|committee-r3|members-quant-r2,hist-r1,scout-r2,skeptic-r3|a2a-1.0|sdk-1.3.1|guards-r1|skills-9fd4d88f|out-1024`.
- agent_committee answered 66 of 90 questions; its cost per answered question is 3.18 US$ per 1,000.
- agent_skills: 100.0% of answers were valid JSON on the first try, repair rate 0.0%.
- agent_committee: 95.5% of answers were valid JSON on the first try, repair rate 3.3%.
- agent_skills skills loaded (questions that loaded each skill): electricity-day-ahead 86/90.
- agent_committee: 12 of 90 questions were skipped because the run's own token cap (3,500,000) was used up by the arms before it: a setting of this run, not a property of the forecaster.
- Cost is the run's recorded tokens at the list price of the model, per arm; this result carries the cost of agent_committee.
- Brier of the arms that answered fewer questions is on their answered items only; paired differences use the questions both arms answered (the pair's n).

## What this does and does not show

- Electricity only (the one topic a replay can reproduce), 90 questions from 15 days; the six questions of a day are correlated, so the intervals are day-block intervals.
- One run, one sample of the model's answers; a repeat could differ.
- Weather, Wikipedia, currencies and crypto are judged only on live days.

Paid-call cost: US$0.21.
