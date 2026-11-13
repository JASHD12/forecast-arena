# STAR stories (Situation, Task, Action, Result)

Real incidents from this project, recorded in `docs/project/PROGRESS.md`, `docs/project/DECISIONS.md` and the git
history. Tell them in about 90 seconds each. Be ready for "what would you do differently".

## 1. The eval harness caught a silent truncation

- **Situation.** The LLM forecasters answer in strict JSON. Before trusting them live I
  built an evaluation harness: a frozen golden set of past questions sent to the real
  model by a manual workflow, under a hard token cap.
- **Task.** Find out whether the prompts and the output contract work on the real model,
  cheaply, without touching the live record.
- **Action.** The first run reported valid JSON on the first try for only 17% of
  `llm_plain` answers and a repair rate of 83%, and many calls stopped on `max_tokens`. The
  model thinks before it answers, and the 400-token output cap cut it off mid-answer. I
  made the cap a setting (default 1024 in the workflows), put it into every forecaster's
  version string so the change is visible on the site, and reran the same golden set.
- **Result.** 100% valid JSON on the first try for both forecasters and a 0% repair rate,
  at a cost shown in `numbers.md`. Lesson: measure stop reasons, not just success rates.

## 2. Every live agent answer failed on day one

- **Situation.** On the first real morning run the ledger showed `error` skips for all
  three questions sampled for the tool-using agent, while the simpler LLM forecasters
  answered.
- **Task.** Find the cause without breaking the rules: no editing the ledger, no live API
  calls from my machine.
- **Action.** The skip details held the API message: thinking blocks in the latest
  assistant message "cannot be modified". The trace showed the first call had hit the
  output cap, so the agent re-sent that turn. Our adapter serialized it with a function
  that drops null fields, so the replay differed from what the API had returned; with
  tools in the request the API checks those blocks. I switched to the SDK's exact wire
  form and wrote a regression test that fails on the old code.
- **Result.** Fixed before the next morning run; the failed skips stay in the ledger,
  because the record is append-only. Lesson: replay provider responses byte for byte, and
  have a cheap real-API smoke test for the multi-turn path.

## 3. A Kubernetes pod crash-looped because of an environment variable I never set

- **Situation.** CI applies the Kubernetes manifests to a throwaway kind cluster and
  smoke-tests the API. The pod went into CrashLoopBackOff.
- **Task.** Make the deployment start, without weakening the strict configuration check
  that rejects unknown `ARENA_*` variables (it catches typos in production).
- **Action.** The logs showed an unknown setting `ARENA_API_SERVICE_HOST`. Kubernetes
  injects `<SERVICE>_SERVICE_HOST` variables for every Service in the namespace, and my
  Service was called `arena-api`. I set `enableServiceLinks: false` on the pod and renamed
  the Service so no injected name can start with the prefix.
- **Result.** The kind job went green and the strict check stayed. Lesson: platform
  defaults can collide with your own naming conventions; read the logs before relaxing a
  check.

## 4. CI never started, and nothing in the code was wrong

- **Situation.** Early on, every GitHub Actions run failed within seconds without a
  runner ever starting a job.
- **Task.** Unblock CI, scheduled jobs and Pages, which the whole project depends on.
- **Action.** Jobs failed before any step ran, so the workflow files were not the
  cause; it was an account-level block (the Actions budget and a billing lock). I wrote
  exact steps for the account owner in `docs/project/HUMAN_TODO.md` instead of trying workarounds. Meanwhile I kept working on tasks that
  only needed the offline test suite.
- **Result.** Once the account setting was fixed, the same commit went green with no code
  change. Lesson: separate "my bug" from "my platform" quickly, and keep work flowing.

## 5. Working inside a locked-down network

- **Situation.** The build environment only reaches approved hosts. The pretrained
  time-series model's weights and the eval result downloads came from hosts that were
  blocked.
- **Task.** Use the model and the eval results without disabling security controls.
- **Action.** For the model I turned off the hub's alternative transfer protocol and asked
  for exactly one extra download host to be allowed, with the reason. For the eval results
  the workflow now prints the result JSON into its log, which I could read, so no artifact
  download is needed.
- **Result.** Both worked with one narrow allowlist change. Lesson: ask for the smallest
  permission and redesign the flow when a permission is not worth asking for.

## 6. Two tools that could not share an environment

- **Situation.** dbt's dependencies required an older version of a date library than
  the rest of the project pins.
- **Task.** Add dbt models and tests without loosening the project's pinned lock file.
- **Action.** I gave dbt its own requirements file and virtual environment, built in its
  own CI job, and disabled its anonymous usage statistics.
- **Result.** The main lock file stayed strict, and the marts and their tests run in CI.
  Lesson: isolate tools with conflicting dependencies instead of forcing one environment.
