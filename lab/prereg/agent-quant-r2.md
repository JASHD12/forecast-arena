# Pre-registration: `agent_quant` r2, a better reference estimate and a prompt that may move away from it (T399)

Experiment id: `llm-quant-r2`. Registered 2026-11-28, **before any code of this version exists and before any model call**.
Nothing here changes a live forecaster (integrity rule I8): `quant-r2` is a new revision string of experimental forecasters that are
off. `agent_skills` and `agent_committee` build on this estimate and get their own pre-registrations after it (T400, T401).

## Why (what the first evaluation and a code read showed)

On the 90 November power questions `agent_quant` r1 scored Brier 0.1369 against 0.1302 for `agent` (paired difference -0.0067 in
favour of `agent`, interval [-0.0213, +0.0083] in the other direction's sign convention of `docs/lab/agent-skills.md`, no benefit
shown). A read of `src/arena/agent/quant.py` and the stored answers found three causes:

1. The r1 reference estimate is weak. It averages the share of stored days over a threshold that is by construction a median of the same
   window (so one third of the estimate is about 0.5), the share over the last 7 days, and a binary "latest day crossed". It has no
   distance-to-threshold term.
2. `up_vs_today` is mis-specified. The threshold is set to the latest day's own mean, so "latest day crossed" is always false, and the
   window share measures a level, not the day-to-day change the question asks about.
3. The r1 prompt (`agent_system_v3`) says to start from the estimate and to move only for evidence it cannot see (news). The replay has
   no news, so the model has no licence to move: 58% of its answers were within 0.05 of the estimate.

Disclosure: the author of this registration had seen the November aggregate results of r1 and, from the code read, an in-sample
check of a persistence estimate on the November items. **The design below was chosen on the October set only**
(`evals/golden/power-2026-10.jsonl`, 186 items, built before any run). The November set (`power-2026-11a.jsonl`, 90 items) is used once,
as the confirmatory test, after the code is frozen.

## Changes (revision `quant-r2`)

- **Estimate for the gt and lt templates** (`mean_gt`, `max_gt`, `min_lt`, `spread_gt`, `evening_gt`): persistence with a normal error.
  Centre = the latest stored day's value of the statistic. Standard deviation = the standard deviation of the day-to-day differences of
  that statistic in the stored window, times the square root of the number of days between the latest stored day and the target day.
  Probability through `normal_probability`, clipped to [0.05, 0.95].
- **Estimate for `up_vs_today`**: probability that the next day's mean exceeds the latest day's mean = normal tail of the mean change
  observed for the same weekday of the target day in the stored window, with the standard deviation of all day-to-day changes. Fallback
  to the sd-only (mean change 0) form when the window holds no same-weekday change. The r1 "level" computation is removed.
- **The estimate result names the weekday** of the latest stored day and of the target day (inside the tool result, not in the shared
  context: `render_context` and every live forecaster stay unchanged).
- **Prompt `agent_system_v6`**: the estimate is the starting point, but the model is told to move away from it when the stored data
  disagrees (weekday pattern, the latest hourly profile, distance of the latest value to the threshold) and to say which; the rule "be
  willing to be confident" stays.
- Everything else (tools, limits of 4 research calls and 90 s, sampling, output contract, model) is as in r1.

## Selection (October only; generated, not typed)

Candidates were: the r1 estimate, persistence with a normal error, a weekday-adjusted persistence, a blend of r1 and persistence (gt/lt
templates); for `up_vs_today` the r1 estimate, 0.5, the same-weekday-change form and the share of up days. The rule was "lowest Brier on
the 186 October items, one rule for all gt/lt templates, no per-template exceptions". The numbers are produced by
`scripts/quant_estimate_study.py` into `docs/lab/quant-estimate-r2.md` (a test keeps the card current); they are not repeated here.

## Hypotheses (evaluated once, on the 90 November items, after the code is frozen)

- **H-Q5** (offline, free): the r2 estimate alone has a lower Brier than the r1 estimate alone (paired day-block interval below zero).
- **H-Q6** (paid, primary): `agent_quant` r2 has a lower Brier than `agent` on the same items (paired interval below zero).
- **H-Q7** (cost): cost per question asked at most 1.75 times that of `agent` in the same run (r1 was 1.65 times).
- **H-Q8** (descriptive, expected): `agent_quant` r2 does not beat `ml` on electricity; `ml` is scored on the same items from
  `evals/golden/ml-probs-power-11a.json`.

## Decision rule

H-Q6 and H-Q7 must both hold for `agent_quant` r2 to go to a dry run and the owner's decision; otherwise it stays off and the card says why.
All results are published with intervals, sample sizes and the per-template table, negative ones included. No prompt, threshold or
estimate changes because of how the November items resolved (I8); a further change is a new revision with its own registration. The
paid run (about US$0.2 with `agent` and `agent_quant` r2 on 90 items, from the r1 token counts) needs the owner's OK and lab budget (H46).
