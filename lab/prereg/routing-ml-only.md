# Pre-registration: the `ml`-first routing rule on fresh live days (T327)

Experiment id: `routing-ml-only`. Registered 2026-11-23, before any of the evaluated days exist (SPEC 17, rule L2). Costs nothing: it
only reads forecasts the live arena writes anyway.

## Why

The routing study (`lab/prereg/routing.md`, card `docs/lab/routing.md`) pre-registered a cascade that needed the open fine-tuned model to be
decisive; it never was, so the pre-registered rule saved nothing and the live `llm_router` was not built. A simpler rule, answer with `ml`
alone when it is decisive and use the paid forecaster only otherwise, looked good in the study (on 276 power test questions, delta 0.15:
76.1% of paid calls avoided, Brier 0.1565 against 0.1802 for the paid model and 0.1663 for `ml`). It was chosen **after** looking at a grid
of twelve points on those questions, so it is a hypothesis, not a result. This registration tests it on days that did not exist then.

## Method

- Rule, fixed now and not tuned: `ml_only` with delta = 0.15. For each question that has both a live `ml` forecast and a live
  `llm_context` forecast (Claude, the daily sample): use `ml` if |p_ml - 0.5| >= 0.15, otherwise use `llm_context`. A question the rule
  answers with `ml` is a paid call avoided.
- Data: live questions of batch days 2026-11-24 to 2026-12-23 (30 days, all five topics), resolved and not voided, read from the public
  ledger. Nothing else is selected; days with no sampled question simply contribute nothing.
- Arms on the same questions: the rule, `llm_context` alone, `ml` alone, the base rate.
- Metrics: Brier of each arm, share of paid calls avoided, paired day-block intervals of the rule against `llm_context`, `ml` and the base
  rate (`arena.scoring.stats`). Reported overall (primary) and per topic (descriptive).

## Hypotheses

- **H-ML1**: the rule avoids at least 50% of the paid calls and its Brier is not worse than `llm_context` by more than 0.01 (the paired
  interval's upper bound is below +0.01).
- **H-ML2** (descriptive): the rule is not worse than `ml` alone (the interval against `ml` includes zero or is below it).
- **H-ML3** (expected negative): the saving is smaller outside electricity, where `ml` is rarely decisive.

## Decision rule

Whatever the numbers, they are published with intervals and the sample size. Nothing changes live (I8). If H-ML1 holds on at least 150
questions, the next step is a separate, owner-approved pre-registration for a live `llm_router` using this rule; if it does not hold, the
router stays closed and this card says so. The evaluation is run once, after 2026-12-23 and after those days have resolved.
