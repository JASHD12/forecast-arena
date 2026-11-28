# Pre-registration: the live comparison of the experimental agents with `agent` and `ml`

Experiment id: `live-agents-comparison`. Registered 2026-11-28, **before any of the compared forecasters has a live record that counts**
(`agent_skills` publishes live from the first morning run after its launch; `agent_analyst`, `agent_quant`, `agent_committee` and the
other experimental forecasters do not publish yet). Rule I8 applies from the first live day: no prompt, skill, estimate or threshold of a
compared forecaster changes during its window; a change is a new version and restarts the window.

## Why

The replays (electricity, `docs/lab/*`; Tier C, `lab/prereg/tier-c-weather-attention.md`) have no news backend or retriever, cover few days
and could not separate effects of about 0.005 Brier. The live record has everything the replay lacks (news, all five topics, real
tools) and costs nothing extra. It is the test that decides.

## Who and when

- **Compared forecasters:** every experimental forecaster that publishes live (`agent_skills` from its launch on 2026-11-28; any other,
  such as `agent_analyst`, only from the day the owner switches it on, and its window starts that day).
- **Reference forecasters:** `agent` (the live tool-using agent, the baseline an experimental agent has to beat), `ml` and `base_rate`.
- **Window:** a forecaster's own official batch days (days on or after 2026-11-23, rehearsal excluded), from its first published day.
  Evaluated **once**, on its 30th official day; there are no interim looks except health (skips, `budget_exhausted`, token use).
- **Questions:** those that the compared forecaster and the reference both answered (the daily LLM sample, about 15 a day at three per
  topic), so the pairs are on identical questions. Skips are counted and reported, never filled (I6).

## Hypotheses (paired day-block 95% intervals; overall first, then per topic as descriptive)

- **H-L1** (primary): the forecaster has a lower Brier than `agent` (interval entirely below zero).
- **H-L2**: the forecaster is not worse than `ml` (interval not entirely above zero), overall.
- **H-L3** (descriptive): the same comparisons per topic (power, weather, Wikipedia attention, exchange rates, crypto); with the
  common-group rule that a topic with fewer than 30 common questions is "too early to tell".
- **H-L4** (cost and safety): the forecaster's tokens stay inside the daily cap on every day (no `budget_exhausted` skip on a core
  forecaster) and its cost per question is at most 1.5 times `agent`'s.

## Decision rule

- If H-L1 and H-L4 hold: the forecaster is a candidate for the experimental board's headline mention; any step beyond that (adding it to the
  common group, changing the ensemble) is the owner's decision and needs its own registration.
- If H-L1 does not hold at day 30: it stays experimental with the result published; the owner decides whether to switch it off. The result
  is not re-run on the same days and no change is made because of it (I8).
- A day on which the forecaster causes a `budget_exhausted` skip on a core forecaster is an incident: the owner is told and the flag
  is the owner's to set; the agent does not change flags.

## Limits

One window, one sample of days; a regime change in the data inside the window is possible; topics other than power have few questions a day,
so per-topic intervals will be wide for a long time. The comparison says nothing about days outside the window.
