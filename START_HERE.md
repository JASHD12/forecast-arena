# START HERE - Forecast Arena agent kit

This kit lets a coding agent build Forecast Arena largely on its own. You set it up once,
start it, and check in briefly. Read this page fully before you start; it takes ten minutes.

## What is in the kit

| File | Who reads it | Purpose |
|---|---|---|
| `START_HERE.md` | you | This guide |
| `KICKOFF_PROMPTS.md` | you | The exact text to paste to start the agent |
| `HUMAN_TODO.md` | you and the agent | The few things only you can do |
| `AGENTS.md` | the agent | Operating manual: session protocol, rules, safety rails |
| `CLAUDE.md` | Claude Code | Imports `AGENTS.md`; lists the approvals **you** are giving |
| `docs/SPEC.md` | the agent (and you) | What gets built, in full detail |
| `TASKS.md` | the agent | 76 ordered tasks, each with a pass/fail check |
| `PROGRESS.md`, `DECISIONS.md` | the agent writes, you read | State and reasoning between sessions |
| `scripts/status.py` | both | Prints what is open, ready, blocked, and next |
| `.claude/settings.json` | Claude Code | Optional hard blocks on destructive commands |

## What "without my intervention" really means

Be realistic about three things.

1. **Not zero.** You do about 45 minutes of setup, a five-minute check most days, and a
   handful of things an agent must not do for you: creating accounts, adding an API key,
   writing your legal notice, recruiting classmates.
2. **The agent stops and resumes.** It works until your usage limit is reached, waits for
   the reset, and continues. That works well but not perfectly; see "What stops it" below.
3. **You must understand what it built.** Interviewers will ask how the project works.
   The agent writes an explainer after every phase in `docs/explainers/`. Read each one.
   Say openly that you built it with an AI coding agent and directed the design; hiding
   that will not survive an interview.

## One-time setup

1. Do items **H01, H02 and H03** in `HUMAN_TODO.md`, and tick them.
2. **Read `CLAUDE.md`.** The "standing approvals" in it are permissions you are giving the
   agent in your name: pushing to `main`, and committing automation that publishes the site
   and uses your LLM key inside GitHub. Remove any you do not want; the agent will then
   stop and ask at that point.
3. Keep the working folder clean: it should contain only this repository. For extra
   safety, run the agent in a separate user account, a virtual machine or a container.
4. In the repository folder, run `python scripts/status.py`. You should see
   `NEXT_TASK=T001`.

Later, without hurry: H04 (LLM key, with a spending limit set first), H05 (About and
legal text), H06 (human panel). The agent keeps working on other tasks until then.

## Starting the agent

These instructions are for Claude Code, checked against its documentation in November
2026. Features change, so confirm on the linked pages. For another agent, use prompt C in
`KICKOFF_PROMPTS.md`; how it runs unattended will differ.

### Option A - one long local session (simplest)

1. Open a terminal in the repository folder and start Claude Code in auto mode:
   `claude --permission-mode auto`
   In auto mode a separate safety classifier reviews actions instead of asking you each
   time. It lowers risk; it does not remove it.
2. Paste prompt A from `KICKOFF_PROMPTS.md`. It uses `/goal`, which makes the agent start
   a new turn by itself until the goal is met, instead of stopping after each step.
3. Leave the terminal open and stop the computer from sleeping.

When your session limit is reached, a subscription session can wait and continue by
itself after the reset. Check that "Continue automatically at usage limit" is on in
`/config` (the setting is `autoContinueAtUsageLimit` in your user settings). In the
desktop app, tick "Auto-continue when limits reset" on the limit card instead.

### Option B - scheduled cloud runs (your computer can be off)

Claude Code can run a saved prompt in the cloud on a schedule (the docs call these
scheduled tasks, formerly routines). Create one for this repository with prompt B from
`KICKOFF_PROMPTS.md`, every five or six hours. Before relying on it, check three things in
the current docs: your plan's daily run allowance, the minimum interval, and whether the
task may push straight to `main` (if it can only open pull requests, someone has to merge
them, which defeats the purpose).

### Which to choose

Start with option A for the first day so you can watch it work. Move to option B, or
keep A, once you trust it.

## Your daily check (five minutes)

1. Read the top of `PROGRESS.md`.
2. Run `python scripts/status.py`. Look at `NEEDS_HUMAN` and `BLOCKED`.
3. Open the live site once it exists.
4. Look for open issues labelled `incident` in the repository.
5. Read any new explainer.

If something looks wrong, tell the agent in plain words. It records the correction.

## What stops it, and what to do

| What you see | What to do |
|---|---|
| Limit reached, countdown shown | Nothing. Leave the session open. |
| "Press enter to continue" after the computer slept | Press Enter. |
| Automatic continuing stopped after repeated limit hits | Send any message, for example `continue per AGENTS.md`. |
| Your weekly limit is reached | It will not resume by itself. Wait for the weekly reset, then paste prompt A again. |
| `OPEN_AGENT_TASKS=0` but tasks remain | Everything left is waiting for you or for a date. Tick what you have done in `HUMAN_TODO.md` and paste prompt A again. |
| A task is marked `BLOCKED(permission: ...)` | The safety system refused something. Read the entry in `HUMAN_TODO.md`; approve it in a normal session if you agree. |
| Terminal was closed | Start Claude Code again in the folder and paste prompt A. Nothing is lost; the state is in the files. |

## What to expect, and when

- **First sessions:** skeleton, ledger, electricity questions, baselines, first live run.
  The site appears with a "rehearsal" banner.
- **After five clean days in a row:** the official record starts automatically. That date
  is fixed for good, which is what makes the track record credible.
- **Following weeks:** more domains, the ML models, then the LLM forecasters once you
  have added a key, then statistics, monitoring, the ensemble and the human panel.
- **About 30 official days in:** enough data for the leaderboard to say something.

Autonomous building uses a lot of your plan's allowance. On a smaller plan it will spend
much of its time waiting for resets; that is normal.

Put the project on your CV once it has run officially for two weeks. Use only numbers
printed by `arena report cv`, which reads them from the public record.

## Things the agent will never do, by design

Create accounts, handle money, touch secrets, change repository settings, force-push,
rewrite the public record, invent results, or work around a refused action. If you see
any of these, stop it and tell me.

## Where the Claude Code facts come from

- Permission modes and auto mode: https://code.claude.com/docs/en/permission-modes
- Keeping a session working with `/goal`: https://code.claude.com/docs/en/goal
- Scheduled cloud tasks: https://code.claude.com/docs/en/routines
- `CLAUDE.md` and importing `AGENTS.md`: https://code.claude.com/docs/en/memory
- Settings, including `autoContinueAtUsageLimit`: https://code.claude.com/docs/en/settings-reference

The details of automatic continuing after a limit (the wording of the prompts, how often
it re-arms) come from secondary write-ups, not from a page I could open directly, so treat
the table above as a guide and trust what your own session shows.
