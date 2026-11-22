# Pre-registration: cost routing between cheap and paid forecasters (T250)

Experiment id: `routing`. Registered 2026-11-22, **before** Claude's answers on the test sets exist (SPEC 17, rule L2). Owner approval of
the one paid run that produces them: HUMAN_TODO H31 (2026-11-22).

## Question

A cascade answers with cheap forecasts when they are confident and sends only the unsure questions to the paid model. How many paid
calls could it avoid, and what does that cost in Brier score?

## Method

- Items: the 276 frozen test questions (`evals/golden/power-2026-10.jsonl`, `power-2026-11a.jsonl`), the same as the QLoRA and DPO
  evaluations.
- Forecasts, all computed before the study: `ml` (the power champion, backtest rows), `ft` (the open fine-tuned GGUF with its pinned
  calibration, `lab/artefacts/llm_local_ft.margins.json`), the base rate, and Claude `llm_context` from one capped paid run
  (`lab-routing.yml`, about US$0.15, hard token cap).
- Primary rule, fixed now: `pair` with delta = 0.15 and gamma = 0.10. Answer with the mean of `ml` and `ft` when both are decisive
  (|p - 0.5| >= delta) and agree (|ml - ft| <= gamma); otherwise escalate to `llm_context`.
- Descriptive grid, not a selection: delta in {0.05 ... 0.30} for `pair` and for `ml_only` (answer with `ml` alone when decisive).
- Metrics: Brier of each arm, share of paid calls avoided, paired day-block intervals of the primary rule against `llm_context`, `ml`
  and the base rate.

## Hypotheses

- **H-RT1**: the primary rule avoids at least 30% of the paid calls with a Brier within +0.01 of `llm_context` (an interval that
  includes zero).
- **H-RT2**: the open fine-tuned model is too close to a coin flip to be decisive, so `pair` escalates almost everything and `ml_only`
  saves more. This is the expected outcome.

## Decision rule

Nothing changes live because of this result (I8). A live `llm_router` forecaster (T273) is only built if H-RT1 holds, with delta and
gamma frozen in its version string. A negative result is published.
