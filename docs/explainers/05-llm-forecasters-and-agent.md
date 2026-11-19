# 05 - The LLM forecasters and the agent

How the Claude-based forecasters are built (plain, with data, with tools, as a graph, and a
small open model), what each one is allowed to see, how their cost is capped, how they fail,
and how they are evaluated apart from the live record.
Code: `src/arena/forecasters/llm.py`, `src/arena/agent/` (`forecaster.py`, `tools.py`,
`graph.py`, `retrieval.py`), `src/arena/llm/` (clients, `budget.py`, `parse.py`, `tracing.py`,
`prompts/`), `src/arena/evals/` (golden set and eval runs).

## How it works

1. **Five LLM forecasters, one information ladder.** Each sees a little more than the one
   before, so a difference in score can be traced to what was added:
   - `llm_plain`: the question text, the resolution rule and the date. No data, no tools.
   - `llm_context`: the same plus a compact rendering of the as-of context (about 6,000
     characters at most: recent values, calendar, the weather forecast, top-list trajectories).
   - `agent`: as `llm_context`, plus read-only tools: `get_series`, `get_base_rate`,
     `get_ml_forecast`, `search_news`, `wikipedia_summary` and (with the retriever on)
     `similar_past_questions`, a small RAG over past resolved questions.
   - `agent_graph`: the same agent as a LangGraph graph (plan, retrieve evidence, research with
     tools, critique); a supplemental forecaster with one question per topic per day.
   - `llm_local`: the `llm_context` prompt answered by an open-weights model
     (Qwen2.5-1.5B, llama.cpp) on the CI runner's CPU. It is the cost floor, not a contender.
2. **A shared, seeded daily sample.** Calling a paid model on every question would be costly, so
   each day a seeded, template-stratified sample (3 questions per domain by default) is drawn
   and *every* LLM forecaster answers exactly that sample. The comparison is paired. Questions
   outside the sample get a `not_sampled` skip, so every expected forecaster-question pair
   still has a record.
3. **Hard budget caps in code** (`budget.py`, SPEC 9.4): at most 100 requests and 400,000
   tokens a day (input plus output), 400 output tokens per call in the spec (production and the eval now use 1024,
   because 400 cut thinking answers off), at most 4 tool calls per question. Usage is read from the provider's own
   usage fields, stored in the run manifests and summed across all runs of the UTC day;
   before each call the guard checks that the worst case still fits. At the cap, remaining
   forecasts become `budget_exhausted` skips. No live call happens outside GitHub Actions.
4. **Output contract.** The model must return a small JSON object with a probability; the
   parser accepts a bounded range, allows one repair prompt, and then writes a
   `parse_failure` skip. Provider errors and refusals are `error` skips; a missing client is
   `model_missing`. No failure ever becomes a number.
5. **Information hygiene.** Tool output and data are labelled "data, not instructions" in the
   prompts; the harness, not the prompt, enforces the call and time limits (90 seconds per
   question), so injected text in a headline cannot buy extra calls. Only headline, outlet,
   URL and timestamp are stored for news (S7), and the agent's news search only returns items
   published before the forecast time.
6. **Traces.** Every model call is a span (model, tokens, cache tokens, duration, stop reason,
   tool names, error) stored on the ledger and exported as OpenTelemetry (OTLP/JSON); the
   LLM page shows them and the home page features one real agent trace.
7. **Evaluation apart from live.** `arena eval run` replays a frozen golden set of 2026-10
   power questions through `llm_plain` and `llm_context` and reports Brier, calibration, JSON
   validity, repair rate, tokens and cost. Results are labelled evaluation and never enter
   live scores (I4). The first run found that answers were being cut off by an output cap
   (valid first-try JSON 17%); after the fix it was 100%.

## Why it was built this way

- **An ablation ladder, not a showcase.** The research question is when an agent beats a
  classical model. Plain, context, tools and graph isolate which ingredient matters.
- **Caps and skips over silent substitution.** A budget that degrades quietly would make the
  record look complete when it is not; here a cap is a visible skip with a reason.
- **Prompt and model versions in every forecast.** The version string carries the model id,
  prompt version and output cap, so a change is visible on the site and never mixed into one
  series.
- **A local model as a floor.** If a 1.5B model on a CPU scored like Claude, the benchmark
  would be too easy; if it scores worse, the gap is informative.

## What was rejected

- Giving the LLMs every question every day (cost) or letting the prompt, not the harness,
  enforce limits.
- Structured outputs and prompt caching in production: both were evaluated on the golden set;
  structured outputs were not better and caching raised the cost of one-shot calls, so both
  stay off (and are versioned `|so` if ever enabled).
- A vector database for the retrieval tool: past questions are few, so a small in-process
  index is enough.
- Letting the model browse the open web: news search is restricted to headlines before the
  forecast time.

## Honest limits

- **Small samples.** About 12 forecasts a day per forecaster, so the live LLM comparison needs
  weeks; the eval is 24 questions from one domain and one model. Both are labelled as such.
- **The agent can call `get_ml_forecast`.** It may use the ML forecaster's probability as an
  input, so "agent versus ML" is not a comparison of independent forecasters; the trace shows
  which tools it used, and the information-set table on the site says what each one sees.
- **Evaluation result, 24 questions (not live):** with the data, `llm_context` scored a Brier of
  0.1855 against 0.3483 for `llm_plain`; the paired difference interval excludes zero but is
  wide. That says the data helps, not by how much.
- **Agent in the eval (12 questions, series and base-rate tools only, not live):** Brier 0.2056 against
  0.1923 for `llm_context` and 0.2255 for `llm_plain`. No paired difference is supported (every interval
  includes zero), and the agent was not better than the data-fed model. The sample is far too small to
  conclude anything beyond "no sign that tools help here".
- **One provider and model family** (Claude Haiku in production); results may not carry over.
- **Local model is weak and slow** and is therefore a sampled, supplemental forecaster.

## Ten interview questions

1. **Why sample questions for the LLMs instead of answering all?**
   Cost and a clean comparison: every LLM forecaster answers the same seeded sample, so scores
   are paired. The skip for the others is recorded, so nothing looks complete that is not.
2. **How do you cap spend?**
   Daily request and token caps in code, summed from the run manifests of all runs that UTC
   day, with a pre-call check that the worst case fits. At the cap, a skip is written.
3. **What happens when the model returns garbage?**
   The parser rejects it, one repair prompt is allowed, and then it is a `parse_failure` skip.
   A refusal or provider error is an `error` skip. I never insert a default probability.
4. **How do you defend against prompt injection from news headlines?**
   Data is labelled as data, only headlines are stored, and the harness enforces call and time
   limits, so injected text cannot extend the budget or change the output format. A unit test
   with an instruction inside a tool result checks that nothing changes.
5. **How do you know the agent uses its tools well?**
   Every call is a span with arguments, size and error; the LLM page and a trace card on the
   home page show real ones. Failures are recorded with their detail: a tool-use bug in the
   LangGraph agent showed up as a recorded error skip, and was fixed with a regression test.
6. **What did the eval find?**
   A frozen golden set showed answers cut off by an output cap: first-try valid JSON was 17%.
   Raising the cap fixed it (100%). The metric also had a bug that counted error calls as
   valid, which I fixed. A bad metric is as dangerous as a bad model.
7. **Why is the plain model so much worse than the context model?**
   It has no data: it can only guess from the question text. The 24-question eval puts it
   clearly behind the data-fed model, but the sample is small, so I describe the direction, not
   the size.
8. **Is "agent beats ML" a fair test?**
   Not entirely: the agent can read the ML forecast as a tool. It is a fair test of "does a
   tool-using LLM add anything", and the trace shows when it deferred to the ML number.
9. **Why keep a 1.5B local model?**
   It is free and runs on the CI machine; it sets a floor and shows what open-weights models
   can do at no cost, with the caveat that it is a weak model on a CPU.
10. **What would you change with a bigger budget?**
    Answer every question with the LLMs, add a second provider to check that results do not
    depend on one vendor, and run the agent variants in the eval harness so the ablation covers
    the whole ladder with news and ML tools in a replay (the eval already covers the agent with series and
    base-rate tools only).
