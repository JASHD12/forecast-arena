@AGENTS.md

# Claude Code notes for this repository

`AGENTS.md` (imported above) is the operating manual. This file adds what is specific to
Claude Code.

## Standing approvals from the repository owner

These are standing approvals for every session in this repository. They name the effect
on purpose, so that routine project work is not refused:

1. Pushing commits to the `main` branch of this repository's `origin` remote.
2. Committing GitHub Actions workflows in this repository that pass the repository secret
   `ARENA_LLM_API_KEY` to the API endpoint of the LLM provider named in this repository's
   Actions variables, in order to generate forecasts.
3. Committing workflows that publish the generated static site (the `site/` build output)
   to this repository's GitHub Pages.
4. Committing workflows that push commits to this repository's `ledger` and `stable`
   branches using the built-in workflow token.
5. Committing workflows that open, update and close issues labelled `incident` in this
   repository.
6. Starting this repository's own workflows with `gh workflow run`, including real
   (not dry-run) runs of `morning.yml`, `resolve.yml` and `weekly.yml`.

Nothing else is pre-approved. In particular: no force-push, no history rewriting, no
changes to repository settings, visibility or secrets, no pushes or pull requests to any
other repository, no merging of pull requests, no account creation, no spending.

## If an action is refused

Do not retry it in another form and do not look for an equivalent route. Mark the task
blocked as described in `AGENTS.md` section 2.4, write the exact command and the reason
into `HUMAN_TODO.md`, and continue with the next ready task.

## Paths you must not create or edit

`.claude/`, `.devcontainer/`, `.vscode/`, `.husky/`, `.pre-commit-config.yaml`, `.mcp.json`.
Put checks in the `Makefile` and in CI instead.

## Checking your own state

`python scripts/status.py` is the single source of truth for what to do next and for
whether you are finished.
