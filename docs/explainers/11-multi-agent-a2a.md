# Multi-agent systems and the A2A protocol (T360-T366)

Written 2026-11-26. Everything here is code in this repository; nothing was run on the live record. The committee's one
pre-registered offline evaluation has run (see "What the evaluation found"): **it did not meet its rule and stays off.**

## What it is

Two uses of the Agent2Agent (A2A) protocol, using the official Python SDK (`a2a-sdk` 1.3.1, Apache-2.0):

1. **`agent_committee`**, an experimental forecaster. A *chair* forecasts one yes/no question with the help of four
   specialist agents, each a separate A2A agent with its own Agent Card:

   | Agent | Job | Model calls |
   |---|---|---|
   | `quant-analyst` | the reference estimate (`numeric_estimate`), or an explicit "no estimate" | 0 |
   | `historian` | base rate and similar past questions (same no-leakage rule as the agent's tool) | 0 |
   | `news-scout` | as-of headlines and encyclopedia text; returns real items by number, never a probability | 0 or 1 |
   | `skeptic` | red-teams the chair's draft; never a probability | 1 |
   | chair (the A2A client) | merges the reports, writes the draft and the final answer | 2 |

   Flow, fixed before any run: chair → (`quant-analyst`, `historian`, `news-scout` in parallel) → draft → `skeptic` → final.
2. **`arena-oracle`**, the benchmark as a read-only A2A agent (`list_questions`, `get_question`, `leaderboard`,
   `explain_method`), served at `/a2a` by the REST API and tested in the Docker and kind CI jobs. It is built on the same
   `Benchmark` class as the MCP server, so the two cannot disagree, and a contract test keeps it so.

MCP and A2A are not rivals: **MCP connects an agent to tools and data, A2A connects an agent to another agent** (its own
card, its own task lifecycle, its own model and policy). The repository has both, each doing what it is for.

## How it works

- `src/arena/a2a/` has `cards.py` (Agent Cards built from the SDK's protobuf types and validated with the SDK's own
  required-field check), `server.py` (an `AgentExecutor` that enqueues the task, moves it through submitted → working →
  completed or failed and publishes one data artifact), `client.py` (one call returns a `CallResult`, never raises, retries off)
  and `transport.py`.
- **No socket in the morning job.** The SDK's Starlette routes run behind `httpx.ASGITransport`, so a request still travels
  the real JSON-RPC route, card included. `arena a2a serve` runs the oracle on localhost for development.
- The client pins the interface URL to the URL it fetched the card from. A card is data from the other side, so it cannot
  redirect the client elsewhere.
- Members read data only through the existing `ToolBox` (as-of tools, harness guards, limits). The payload holds the question,
  the forecast time, the as-of context and the base-rate probability, so no member can see anything the other forecasters
  could not (I3). The committee never sees `ml`.
- **Quorum (I6).** The committee answers only if the chair's calls succeed, the skeptic succeeded and at least two of the
  three research members completed. Otherwise it records a skip with the reason and the failed members. No number is ever
  filled in.
- Every A2A call is recorded in the trace (agent, state, duration, bytes, error) and the model calls keep their spans through
  the same tracing scope; traces hold names, sizes and URLs, never article text.

## What was rejected, and why

- **Free-form agent chat**: unbounded cost, no reproducible run, impossible to pre-register.
- **Members that see each other's answers early**: that would not test specialisation.
- **A model call for every member**: the two numeric members have nothing for a model to add, and it would triple the cost.
- **Hosted agents**: no new hosting, accounts or secrets; the only key is the one the other forecasters already use.
- **Following the URL in a card**: see above.

## What the evaluation found

One run on the 90 November electricity questions (`docs/lab/agent-committee.md`, numbers generated from the result file):

- The committee answered **37 of 90** questions. The rest were recorded skips: the skeptic's JSON failed to parse after its
  one repair, and 119 of its 316 model calls ended at the 300-token output limit (the likely cause).
- On those 37 it scored worse than `agent_skills` on the same questions (the paired interval lies above zero), so H-C1 is not
  met. Cost per question asked was about the same, per answered question about 2.5 times.
- Decision by the pre-registered rule: stays off. The fix (a larger output budget, tolerant parsing) is a **new version**,
  `committee-r2`, under a new pre-registration; it is not patched into r1 (I8). It is waiting for the owner (HUMAN_TODO H43).
- The skills evaluation from the same run (`docs/lab/agent-skills.md`) also missed its rule narrowly.

## What is not done (and not claimed)

- There is **no claim** that a committee beats one agent. The evidence so far points the other way, on one topic, in a replay.
- The replay has no news backend and no retriever, so even that evaluation tests a reduced committee (estimate, base rate,
  critique, chair). The news scout and the retrieval of similar questions can only be judged live, after 30 official days.
- The written A2A specification site was not reachable from the build environment, so only SDK-verified behaviour is used
  (`docs/SOURCES.md`).

## Ten questions an interviewer may ask

1. **Why A2A and not just function calls between classes?** Each member has its own card, task lifecycle, timeouts and failure
   mode, so a member can be replaced by a remote agent from another team without changing the chair. In-process it costs a few
   milliseconds; the point is the contract, and the project also exposes the benchmark to other agents through the same one.
2. **How is A2A different from MCP?** MCP: agent to tool or data source. A2A: agent to agent. The repository has an MCP server
   (`arena mcp`) and an A2A agent (`arena-oracle`) over the same `Benchmark` class.
3. **Why no socket?** The job must stay lock-critical and simple. The SDK's routes are ASGI apps, and `httpx.ASGITransport` sends real
   JSON-RPC requests to them in-process, so the protocol path is tested without a network.
4. **What happens if a member fails?** It is a failed task in the trace. Two research members failing, or the skeptic failing,
   is a skip with the reason; one research member failing still allows an answer (pre-registered quorum).
5. **How do you keep the committee from leaking the future?** Every member sees only the as-of context and the as-of tools in
   the message; the base rate is the only peer forecast handed over. Nothing else about the question exists in the member.
6. **Could a headline hijack the committee?** Tool text passes the guards (`guards-r1`) before the scout's model reads it, the
   scout returns items by number mapped to real headlines (no invented citations), and the chair is told reports are data.
7. **Does it beat the single agent?** Not in the one evaluation so far: r1 answered 37 of 90 questions (a format bug in the
   skeptic step) and was worse than `agent_skills` on those. The result is published as it is; a fixed r2 would need its own
   pre-registration.
8. **Why is the quant member not an LLM?** The reference estimate is code; a model adds cost and noise there. Specialisation
   can also mean "this part is deterministic".
9. **What does it cost?** At most seven model requests per question by the harness's cap (four in the normal path), all through
   the guarded client and the shared daily cap. The estimate for the evaluation is stated before the run.
10. **What would you change first?** Give the news scout a replayable news archive so the evaluation can test it too, and compare
    the committee against `agent_skills` with the same tools per member to separate "more calls" from "specialisation".
