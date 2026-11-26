# Pre-registration: a committee of specialist agents over A2A (T361)

Experiment id: `agent-committee`. Registered 2026-11-26, **before `agent_committee` has run on any item** (SPEC 17, rule L2). Evaluation only:
nothing here changes `agent`, `agent_graph`, `agent_hybrid`, `agent_quant`, `agent_skills`, `llm_context` or `llm_plain` (integrity rule I8). It follows
`lab/prereg/agent-skills.md` and uses the same items, caps and metrics so the arms are comparable.

## Question

Does a committee of specialists, each owning one job and talking to the chair over the A2A protocol, forecast better than one generalist agent that has the
same data, the same skills and a comparable token budget? An honest "no" (or "yes, but at three times the cost") is a valid result.

## What is tested

`agent_committee` (experimental, off by default). Five agents, each an A2A server with its own Agent Card; the chair calls the others as an A2A client.

| Agent | Job | Model calls |
|---|---|---|
| `quant-analyst` | the deterministic reference estimate (`numeric_estimate`) for the question and the name of the topic skill; "no estimate" for topics without a reference model | none |
| `historian` | the base rate and the similar past questions (same leakage rule as the agent's tool), as evidence items | none |
| `news-scout` | as-of headlines and Wikipedia text through the existing tools and guards, then one model call that keeps the relevant items and says in a line what each could change; **never returns a probability** | 1 |
| `skeptic` | red-teams the chair's draft (threshold or comparator mistakes, hedging, overconfidence, a number that disagrees with the estimate without a reason); never returns a probability | 1 |
| `chair` | merges the members' artefacts, writes a draft, then the final answer in the standard output contract (`parse_answer`, one repair retry) | 2 |

Fixed message flow per question: chair → (`quant-analyst`, `historian`, `news-scout` in parallel) → chair draft → `skeptic` → chair final.
Members get only the question fields, the as-of context and the as-of time in the A2A message, and read tools only through the existing `ToolBox` (I3).
At most four model calls per question (plus one repair), all through the guarded client and the shared 300,000-token daily cap.

## Quorum rule (fixed now, I6)

- The committee answers if the chair's two calls succeed, the skeptic's call succeeded and **at least two of the three research members** (`quant-analyst`,
  `historian`, `news-scout`) completed their task. "Completed with no estimate" or "no evidence found" is completed; an error, a timeout or a refusal is a failure.
- Otherwise it records a skip with the reason (`error`, `parse_failure` or `budget_exhausted`) and the failed members' names. It never inserts a number.
- Every member's task state, duration, size and sources go into the trace (names, sizes and URLs only, no article text).

## Data and replay limits

- Items: `evals/golden/power-2026-11a.jsonl` (90 questions, primary; outside the skill tables' window) and, only if the owner approves a second run, a seeded
  subset of `power-2026-10.jsonl` (secondary). Arms on identical items: `agent_committee`, `agent_skills` (comparison), plus the golden base rate.
- **The replay has no news backend and no retriever.** In the replay the `news-scout` therefore returns "no evidence available" and the `historian` returns the
  base rate only. The evaluation tests a **reduced committee** (numeric estimate, base rate, critique, chair) and says so on the card; the news-scout and the
  retrieval of similar questions can only be judged on live days (after at least 30 official days), never on the replay.
- Weather, Wikipedia, currencies and crypto cannot be replayed faithfully; they are judged only live (as in `agent-skills.md`).

## Hypotheses

- **H-C1**: the committee has a lower Brier than `agent_skills` on the November items (paired day-block interval of the difference below zero).
- **H-C2**: its cost per question is at most 2.5 times `agent_skills`'.
- **H-C3** (descriptive): which member moves the number and by how much: share of questions where the final probability differs from the chair's draft by at
  least 0.05 (effect of the skeptic), and where it differs from the numeric estimate by at least 0.05 (effect of the other members and the chair), with the sign of
  the change against the outcome. Computed from the traces, no new calls.
- **H-C4** (expected): a committee built mostly from the same information cannot beat `ml` on electricity; reported for context, not decided on.

## Metrics

Brier, log score, valid-answer share and skip reasons, tokens and US$ per question (price table of `arena.site.llm_obs`), A2A task latency per member, paired
day-block intervals on identical items (`arena.scoring.stats`). Result file `evals/results/lab-agent-committee.json` (`LabResult`), card `docs/lab/agent-committee.md`.

## Decision rule

Results are published with intervals and sample sizes, negative ones included. `agent_committee` goes live (experimental, outside the headline board and the
ensemble) only if H-C1 and H-C2 hold and a dry run in an unsealed window stays within the 300,000-token daily cap and the runner-time budget; otherwise it stays
off and the card says why. No prompt, member or quorum rule changes because of how a specific question resolved (I8): a change is a new version string and a new
pre-registration. The paid run happens once, from `main`, with the owner's approval of the exact estimate.
