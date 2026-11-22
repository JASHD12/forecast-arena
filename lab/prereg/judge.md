# Pre-registration: LLM-as-judge for stored rationales (T252b)

Experiment id: `judge`. Registered 2026-11-22, before the judge runs (SPEC 17, rule L2). Owner approval of the paid run: HUMAN_TODO H27.

## Method

- Items: 100 stored live rationales (seeded, round robin over the forecasters; `lab/judge/items.json`, built from the public ledger
  by `arena lab judge-sheet`). The judge never sees the forecaster name.
- Judge: the live model (Claude Haiku) with the fixed rubric in `src/arena/lab/judge.py` (data use, direction, hedging, 1 to 5 each;
  reasoning first, constrained JSON). One pass, hard caps (about US$0.10).
- Human calibration: the owner labels 30 of the 100 items (`lab/judge/label-sheet.csv`, HUMAN_TODO H29). Agreement is quadratic-weighted
  Cohen's kappa per dimension.

## Hypotheses

- **H-JG1**: the judge's mean scores order the forecasters' rationales the same way as their numeric grounding rate (`lab-grounding`).
- **H-JG2**: agreement with the owner is at least moderate (kappa >= 0.4) on every dimension. A lower value means the judge is not
  trusted and is reported as such.

## Decision rule

Report-only; nothing changes live (I8). Without the owner's labels the judge's scores are published without an agreement figure and
labelled as uncalibrated.
