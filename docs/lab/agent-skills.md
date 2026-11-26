# Forecasting skills for the tool-using agent

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-agent-skills.json`, created 2026-11-26T19:57:07.450167+00:00.

Why companies use it: Progressive disclosure of short, reviewed skill notes is how Anthropic and others package domain know-how for agents without growing every prompt; the question is whether it helps a forecaster. (anthropic-skills)

| Variant | Questions | Brier | Log score | ECE | US$ per 1,000 |
|---|---|---|---|---|---|
| agent / eval | 90 | 0.1302 | 0.4178 | 0.1009 | 0.6418 |
| agent_quant / eval | 90 | 0.1369 | 0.4331 | 0.0796 | 1.0608 |
| agent_skills / eval | 90 | 0.1279 | 0.4091 | 0.1057 | 1.3928 |
| base_rate / eval | 90 | 0.203 | - | - | - |

- agent_skills minus agent_quant: Brier difference -0.0090, 95% interval [-0.0204, +0.0028] over 90 questions (interval includes zero).

- Run eval-20261126T195707 of llm-eval.yml on power-2026-11a.jsonl (90 questions), replay with the tools a replay can honour; labelled evaluation, never the live record.
- agent_skills is agent_quant plus load_skill; agent is the live prompt with replay tools.
- Skips per arm: agent none; agent_quant none; agent_skills none. Versions: agent `claude-haiku-5-5|prompt-v1-c431eac3ad4a|tools-4|out-1024`; agent_quant `claude-haiku-5-5|prompt-v1-d5017c1522da|tools-4|out-1024|quant-r1`; agent_skills `claude-haiku-5-5|prompt-v1-78474be2c501|tools-4|out-1024|quant-r1|skills-r1-d011316a`.
- Cost is the run's recorded tokens at the list price of the model, per arm; this result carries the cost of agent, agent_quant, agent_skills.
- Brier of the arms that answered fewer questions is on their answered items only; paired differences use the questions both arms answered (the pair's n).

## What this does and does not show

- Electricity only (the one topic a replay can reproduce), 90 questions from 15 days; the six questions of a day are correlated, so the intervals are day-block intervals.
- One run, one sample of the model's answers; a repeat could differ.
- Weather, Wikipedia, currencies and crypto are judged only on live days.

Paid-call cost: US$0.28.
