# agent_quant r2: a better reference estimate and a prompt that may move away from it

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-agent-quant-r2.json`, created 2026-11-28T16:26:58.770253+00:00.

Why companies use it: Giving an LLM agent a numeric tool and a statistical reference is how companies make tool-using forecasters less hedgy; the question is whether the r2 estimate and prompt fix what r1 got wrong. (anthropic-tool-use)

| Variant | Questions | Brier | Log score | ECE | US$ per 1,000 | US$ per 1,000 answered |
|---|---|---|---|---|---|---|
| agent / eval | 90 | 0.1305 | 0.4158 | 0.0979 | 0.6275 | 0.6275 |
| agent_quant / eval | 90 | 0.1259 | 0.4009 | 0.097 | 1.162 | 1.162 |
| base_rate / eval | 90 | 0.203 | - | - | - | - |

- agent_quant minus agent: Brier difference -0.0046, 95% interval [-0.0210, +0.0127] over 90 questions (interval includes zero).

- Run eval-20261128T162658 of llm-eval.yml on power-2026-11a.jsonl (90 questions), replay with the tools a replay can honour; labelled evaluation, never the live record.
- agent_quant r2 uses the persistence estimate (`quant-r2`) and prompt `agent_system_v6`; agent is the live prompt with replay tools. The replayed ml probabilities were not passed to the arms (the workflow passes them only when agent_analyst is in the run; the agent never called get_ml_forecast in 588 stored traces).
- Skips per arm: agent none; agent_quant none. Versions: agent `claude-haiku-5-5|prompt-v1-c431eac3ad4a|tools-4|out-1024`; agent_quant `claude-haiku-5-5|prompt-v1-c645565dffa4|tools-4|out-1024|quant-r2`.
- agent: 98.9% of answers were valid JSON on the first try, repair rate 1.1%.
- agent_quant: 94.4% of answers were valid JSON on the first try, repair rate 5.6%.
- Cost is the run's recorded tokens at the list price of the model, per arm; this result carries the cost of agent, agent_quant.
- Brier of the arms that answered fewer questions is on their answered items only; paired differences use the questions both arms answered (the pair's n).

## What this does and does not show

- Electricity only (the one topic a replay can reproduce), 90 questions from 15 days; the six questions of a day are correlated, so the intervals are day-block intervals.
- One run, one sample of the model's answers; a repeat could differ.
- Weather, Wikipedia, currencies and crypto are judged only on live days.

Paid-call cost: US$0.16.
