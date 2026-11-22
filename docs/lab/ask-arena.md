# Ask the Arena: tiered chat over the published record

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-ask-arena.json`, created 2026-11-22T23:10:25Z.

Why companies use it: Retrieval-grounded assistants with refusals and tiered routing are the standard pattern for answering questions over a company's own data without inventing facts.

| Variant | Questions | Hit % | False refusals % | No invented numbers % | Correct refusals % |
|---|---|---|---|---|---|
| category: refusal | 16 | 100 | - | - | - |
| category: personal | 3 | 100 | - | - | - |
| category: benign | 6 | 100 | - | - | - |
| category: method | 12 | 83.3 | - | - | - |
| category: board | 5 | 100 | - | - | - |
| category: status | 3 | 100 | - | - | - |
| category: decline | 10 | 100 | - | - | - |
| category: lookup | 30 | 100 | - | - | - |
| category: result | 30 | 100 | - | - | - |
| finance and personal refusals | - | - | - | - | 100 |
| benign questions | - | - | 0 | - | - |
| all answers | 115 | - | - | 100 | - |


- 115 questions on the offline fixture pack (30 questions, 263 document chunks, 227450 bytes).
- Answers by tier: lookup 69, documents 13, declined or refused 33.
- Latency in Node: median 0.7 ms, 95th percentile 8.93 ms.
- Missed in the golden set: 2 question(s); see the failure list in the run output.

## What this does and does not show

- The questions are written by the project owner's agent, so they may not match how visitors phrase things; the rates are not a measure of real-world accuracy.
- 'No invented numbers' checks that every number in an answer occurs in the pack or the question (probabilities as whole percentages); it does not check meaning.
- The forecaster-choice rule is a hypothesis from the routing study; this evaluation does not test whether it picks the better forecaster.
- The fixture pack has only one topic; the live pack has five.

Paid-call cost: US$0.00.
