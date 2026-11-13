# docs/project/KICKOFF_PROMPTS.md - what to paste

Three ways to run the agent. Pick one. `docs/project/START_HERE.md` explains when to use which.

## A. One long local session (Claude Code in a terminal or the desktop app)

Start Claude Code in the repository folder in auto mode, then paste this as one message.
`/goal` keeps the agent working turn after turn until the condition is met.

```
/goal Build Forecast Arena by following the session protocol in AGENTS.md and working through docs/project/TASKS.md in order. The goal is met when all three of these hold: (1) `python scripts/status.py` prints OPEN_AGENT_TASKS=0, (2) `make check` exits 0, (3) `git status --short --branch` shows a clean tree with nothing left to push. Prove it by running those three commands and showing their output. A task counts as done only after its "Done when" checks pass and its commit is pushed to main. Follow the integrity rules and safety rails in AGENTS.md without exception. If the permission system refuses an action, record the exact command in docs/project/HUMAN_TODO.md, mark the task blocked, and move on; never work around a refusal. Standing approvals from the repository owner for this session, as listed in CLAUDE.md: pushing commits to main of this repository; committing workflows in this repository that pass the secret ARENA_LLM_API_KEY to the configured LLM provider's API, that publish the built site to this repository's GitHub Pages, that push to this repository's ledger and stable branches with the built-in token, and that manage issues labelled incident; and starting this repository's own workflows with gh workflow run. Nothing else is pre-approved.
```

To resume after any stop, start Claude Code again in the same folder and paste the same
message. The agent picks up from the files.

## B. Scheduled cloud runs (no computer needed)

Use this as the prompt of a scheduled task that runs every five or six hours. Each run
starts from a fresh copy of the repository, so it relies entirely on the files.

```
Read AGENTS.md and follow its session protocol exactly. Complete as many tasks from docs/project/TASKS.md as you can in this run, in order, committing and pushing to main after each one. Stop when `python scripts/status.py` prints OPEN_AGENT_TASKS=0, or earlier if you are running low on budget. Before you stop, make sure everything is committed and pushed, `make check` passes, and docs/project/PROGRESS.md has a short session summary. Follow the integrity rules and safety rails in AGENTS.md without exception. If an action is refused, record it in docs/project/HUMAN_TODO.md and move on; never work around a refusal. The standing approvals listed in CLAUDE.md apply.
```

## C. Any other coding agent

```
Read AGENTS.md and follow its session protocol. Work through docs/project/TASKS.md in order until `python scripts/status.py` prints OPEN_AGENT_TASKS=0. Commit and push after each task. Never work around a refused action; record it in docs/project/HUMAN_TODO.md instead.
```

## Short messages for later

- After you tick items in docs/project/HUMAN_TODO.md: `I ticked items in docs/project/HUMAN_TODO.md. Re-read it and continue per AGENTS.md.`
- If the session seems stuck: `Run python scripts/status.py, tell me in five lines where you are, then continue per AGENTS.md.`
- To pause cleanly: `Finish or cleanly commit the current task, update docs/project/PROGRESS.md, push, and stop.`
