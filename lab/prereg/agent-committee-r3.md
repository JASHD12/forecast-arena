# Pre-registration: `agent_committee` r3, repairs that work, a fair comparison with `agent_skills`, a skeptic that sees the data (T401)

Experiment id: `agent-committee-r3`. Registered 2026-11-28, **before any code of this version exists and before any model call**.
Nothing here changes a live forecaster (integrity rule I8): `agent_committee` is experimental and off; the new revision strings are
visible in its version. Builds on `lab/prereg/agent-quant-r2.md` (the committee's quant member now serves the `quant-r2` estimate) and
`lab/prereg/agent-skills-r2.md`, the arm it is compared with.

## Why

r2 (`docs/lab/agent-committee-r2.md`) answered 87 of 90 questions and scored +0.0060 against `agent_skills` with a 95% interval of
[-0.0036, +0.0152] (H-C1 not met), at 1.44 times the cost per question asked. A read of the code found:

1. **The chair's repair is blind.** `committee.py` sends the repair instruction without the model's failed reply, so "your previous answer
   could not be parsed" refers to an answer the model cannot see (the single agent sends it). 32% of chair calls needed a repair and only
   68.5% of first answers were valid JSON. The skeptic's retry has the same gap.
2. **The chair's prompts push it past the 80-word rationale limit** that the parser enforces: rule 4 asks to name the members relied on in
   the rationale, and the final prompt asks to say which issue was accepted.
3. **The comparison with `agent_skills` is not like for like.** The committee never sees any skill text (the quant member returns only the
   skill name; the chair has no tools), while `agent_skills` loads the topic skill.
4. **The skeptic cannot check the draft against the data.** It sees only the draft and the reports, never the stored question data, and its
   check 2 treats any gap from the estimate as a problem, although the r1 estimate was weak.
5. Replay limits (unchanged, stated on the card): no news backend, so the news scout answers "no evidence available"; no retriever, so the
   historian gives the base rate only. Building a retriever for the replay needs the embedding model in the eval workflow and is not part
   of this version.

Disclosure: the author had seen the November aggregate results of r1 and r2 when choosing these changes. They are mechanical (a repair
that carries the failed reply, a prompt that no longer asks for what the parser rejects, the topic skill text the comparison arm has, the
data the skeptic was missing).

## Changes (revision `committee-r3`)

- **Repair.** The chair's repair sends the model's failed reply as an assistant turn before the repair instruction. The skeptic's retry
  quotes its previous reply (first 800 characters).
- **Prompts v2** for the chair, the brief, the final and the skeptic. Members are cited in `key_factors`, not in the rationale; the
  brief and the final carry the topic skill text as project-team guidance (not data about the question); the skeptic gets the stored
  question data and checks the draft against it, and a gap from the estimate is a problem only when the data do not support it.
- The skeptic member revision is `skeptic-r3`; the quant member is `quant-r2`; historian and scout are unchanged.
- Not changed: models, member count, quorum rule, output budgets (1,024 tokens for scout and skeptic), the replay's missing news and
  retriever.

## Method and hypotheses (evaluated once, on the 90 November items, after the code is frozen)

One `llm-eval.yml` run on `power-2026-11a.jsonl` with `agent_skills` r2 and `agent_committee` r3 on the same items (the `agent_skills` r2
arm may be shared with the run of `lab/prereg/agent-skills-r2.md`, checked by item and version hash).

- **H-C1''**: `agent_committee` r3 has a lower Brier than `agent_skills` r2 (paired day-block interval entirely below zero).
- **H-C2''**: cost per question asked at most 2.5 times that of `agent_skills` r2.
- **H-C5''**: at least 90% of the questions answered (the rest are recorded skips, never filled in).
- **H-C6** (descriptive): share of chair calls that needed a repair and share of valid first answers, from the saved traces.

## Decision rule

`agent_committee` r3 goes to a dry run and the owner's decision only if H-C1'', H-C2'' and H-C5'' all hold; otherwise it stays off and the
card says why. All results are published with intervals, sample sizes and per-template tables, negative ones included. No change is made
because of how the November items resolved (I8); a further change is a new revision with its own registration. The paid run needs the
owner's OK and lab budget (H46).
