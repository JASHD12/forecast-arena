# Ask the project: cited answers over the project documents

**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**

Result file: `evals/results/lab-docs-assistant.json`, created 2026-11-21T19:20:28Z.

Why companies use it: Retrieval-grounded assistants with citations and refusals are the standard internal-knowledge pattern.

| Variant | Answerable questions | Hit % | False refusals % | Out of scope | Correct refusals % |
|---|---|---|---|---|---|
| docs_assistant | 20 | 60.0 | 5.0 | 6 | 83.3 |


- 26 hand-written questions; answers are extractive sentences.

## What this does and does not show

- The method was changed once after seeing the first score (stop words removed from the query; a hit no longer needs the expected file; the first run scored 25.0% hits), so the final figure is optimistic.
- Small, hand-written question set whose expected phrases come from the same documents.
- A hit means a cited chunk contains the expected phrase, not that the answer reads well.
- Refusal uses a fixed word-coverage threshold chosen once, not tuned per question.

Paid-call cost: US$0.00.
