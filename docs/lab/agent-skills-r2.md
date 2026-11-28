# agent_skills r2: topic-only skills index and skill text matching the new estimate

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-agent-skills-r2.json`, created 2026-11-28T16:26:58.770253+00:00.

Why companies use it: Progressive disclosure of short, reviewed skill notes is how Anthropic and others package domain know-how for agents without growing every prompt; this is the re-test after the cost and anchoring defects of the first version. (anthropic-skills)

| Variant | Questions | Brier | Log score | ECE | US$ per 1,000 | US$ per 1,000 answered |
|---|---|---|---|---|---|---|
| agent_quant / eval | 90 | 0.1259 | 0.4009 | 0.097 | 1.162 | 1.162 |
| agent_skills / eval | 90 | 0.1245 | 0.4003 | 0.0692 | 1.3671 | 1.3671 |
| base_rate / eval | 90 | 0.203 | - | - | - | - |

- agent_skills minus agent_quant: Brier difference -0.0014, 95% interval [-0.0088, +0.0058] over 90 questions (interval includes zero).

- Run eval-20261128T162658 of llm-eval.yml on power-2026-11a.jsonl (90 questions), replay with the tools a replay can honour; labelled evaluation, never the live record.
- agent_skills r2 is agent_quant r2 plus load_skill with a topic-only index (prompt `agent_system_v7`, skills revision 2). The replayed ml probabilities were not passed to the arms (see the agent_quant r2 result).
- Skips per arm: agent_quant none; agent_skills none. Versions: agent_quant `claude-haiku-5-5|prompt-v1-c645565dffa4|tools-4|out-1024|quant-r2`; agent_skills `claude-haiku-5-5|prompt-v1-03d70e91e0e5|tools-4|out-1024|quant-r2|skills-r2-9fd4d88f`.
- agent_quant: 94.4% of answers were valid JSON on the first try, repair rate 5.6%.
- agent_skills: 100.0% of answers were valid JSON on the first try, repair rate 0.0%.
- agent_skills skills loaded (questions that loaded each skill): electricity-day-ahead 86/90.
- Cost is the run's recorded tokens at the list price of the model, per arm; this result carries the cost of agent_skills.
- Brier of the arms that answered fewer questions is on their answered items only; paired differences use the questions both arms answered (the pair's n).

## What this does and does not show

- Electricity only (the one topic a replay can reproduce), 90 questions from 15 days; the six questions of a day are correlated, so the intervals are day-block intervals.
- One run, one sample of the model's answers; a repeat could differ.
- Weather, Wikipedia, currencies and crypto are judged only on live days.

Paid-call cost: US$0.12.
