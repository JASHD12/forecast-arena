# Pre-registration: the committee, version r2 (T368)

Experiment id: `agent-committee-r2`. Registered 2026-11-26, **before r2 has run on any item**, after the owner's "yes, try" (HUMAN_TODO H43).
It extends `lab/prereg/agent-committee.md` (same question, flow, quorum rule, items, metrics and decision rule) and changes only what the first
result pointed at. Evaluation only; nothing live changes (I8): `agent_committee` is off and has no live record.

## Why a new version

The first evaluation (run 45883972017, `docs/lab/agent-committee.md`) is the r1 result and stays published as it is: the committee answered 37 of 90
questions; for the other 53 the skeptic's reply could not be parsed, and 119 of the committee's 316 model calls ended at the 300-token output limit
(`stop_reason: max_tokens`). That is a defect of the implementation, not evidence about the idea. r2 fixes exactly that and nothing else.

## What changes (all visible in the version string, `committee-r2`, `scout-r2`, `skeptic-r2`)

1. The output budget of the two members that call a model (`news-scout`, `skeptic`) goes from 300 to 1,024 tokens (the same limit the evaluation
   gives every other forecaster).
2. The scout's and the skeptic's replies are read by taking the single outermost JSON object (a code fence or a sentence around it is allowed); the
   content is checked as strictly as before. A reply cut off at the limit still fails, and a failure is still a recorded skip.

Not changed: prompts, the flow, the quorum rule, the quant analyst, the historian, the chair, the guards, the tools, the sample, the model. No number
from r1's answers was used to choose these changes beyond the failure reasons above (parse error counts and stop reasons), and none will be used to
change anything after the r2 run (a further change is another version and another pre-registration).

## Data and design

- Same items: `evals/golden/power-2026-11a.jsonl` (90 questions, sha256 `fd31d14b6c5123b30e1c95c18063b28dd41718414af7826d1de02da48801ceac`).
- **Only the committee arm is run** (one `llm-eval.yml` dispatch, `variants=agent_committee`, `limit=90`, token cap 1,500,000). The comparison arm
  `agent_skills` is **not re-run**: its 90 answers from run 45883972017 are reused (same golden file, same hash, checked by the converter), so the
  pairs are on identical questions and the cost of a second `agent_skills` run is saved. This is stated on the card.
- Cost estimate: US$0.15 to 0.25 (r1's committee arm cost US$0.13 for 90 questions of which 37 completed all four calls); hard cap 1,500,000 tokens.
  Lab budget after the run: about US$1.7 of 2.00.
- Replay limits as in the r1 pre-registration: the news scout answers "no evidence available" (no news backend) and the historian gives the base rate
  only. r2 therefore still tests a reduced committee.

## Hypotheses

- **H-C5** (mechanical, checks the fix): at least 90% of the 90 questions are answered (at most 9 skips).
- **H-C1, H-C2, H-C3**: as in `agent-committee.md`. H-C1: lower Brier than `agent_skills` on the questions both answered (paired day-block interval
  below zero); H-C2: cost per question at most 2.5 times `agent_skills`'; H-C3 descriptive.

## Decision rule

H-C5 is reported first: if it fails, the result is "the fix did not work" and H-C1 is reported only for the questions answered. The committee may go to
a dry run in an unsealed window only if H-C5, H-C1 and H-C2 all hold; otherwise it stays off and the card says why. The run is made once.
