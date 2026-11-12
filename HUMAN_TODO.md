# HUMAN_TODO.md - things only you can do

Tick an item (`[x]`) when it is done. The agent reads this file at the start of every
session and unblocks the tasks that were waiting. The agent may add items at the bottom.
Keep the first line of each item in exactly this shape; the status script parses it.

## Before the agent starts

- [ ] H01 · Create the repository and add this kit
  - Create a **public** GitHub repository named `forecast-arena` (public keeps the record
    checkable by anyone and suits free automation minutes; confirm current GitHub terms).
  - Clone it, copy every file of this kit into it (including the hidden `.claude` folder
    and `.gitignore`), commit, and push to `main`.
- [ ] H02 · Install and sign in to the tools
  - `git`, Python 3.12 or newer, the GitHub CLI (`gh auth login`), and your coding agent.
  - Optional: `uv` for faster Python installs. The agent falls back to `pip` without it.
  - Check: `gh repo view` works inside the repository folder.
- [ ] H03 · Turn on GitHub Pages
  - Repository settings, Pages section: set the source to **GitHub Actions**.
  - Needed before the first live run (task T030).

## Needed later (the agent keeps working on other tasks meanwhile)

- [ ] H04 · Choose an LLM provider and add the key
  - Pick a provider and an inexpensive model. **Set a monthly spending limit in the
    provider's console first.** The project's own caps (SPEC 9.4) are a second safety net.
  - In the repository's Actions secrets, add `ARENA_LLM_API_KEY`.
  - In the repository's Actions variables, add `ARENA_LLM_PROVIDER` (`anthropic` or
    `openai_compatible`), `ARENA_LLM_MODEL` (the exact model id), and, only for
    `openai_compatible`, `ARENA_LLM_BASE_URL`.
  - Never paste the key into a chat, a file, or a commit.
  - Needed for tasks T064, T065, T068.
- [ ] H05 · Write the About and legal text
  - `site_content/about.md`: who you are, a link to your profile, how the project was built.
  - `site_content/legal.md`: check what a website published from Germany must show
    (a provider identification and a privacy notice are commonly required). This is your
    responsibility to confirm; the agent must not invent legal text.
  - Until then the site shows a placeholder.
- [ ] H06 · Recruit the human panel
  - Ask 10 to 15 classmates to forecast once a week. Follow `docs/PANEL_SETUP.md` (the
    agent writes it in task T091): create the form, hand out tokens, publish the sheet as
    CSV, and add the link as the Actions variable `ARENA_PANEL_CSV_URL`.
  - Tell the panel what is stored (a pseudonym and their probabilities) and get their
    agreement. No names or emails go into the repository.
  - Needed for task T092.
- [ ] H07 · Write your interpretation of the findings
  - After at least 30 official days: `site_content/findings.md`, in your own words. What
    surprised you, what you would change, what the results do not show.
- [ ] H08 · Optional decisions (default is no)
  - A second market domain with an equity index, only if you find a data source whose
    terms clearly allow it.
  - A remote experiment-tracking server.
  - Record your answer in `DECISIONS.md`.

## Recurring

- [ ] H09 · Review (about five minutes a day at first, then twice a week)
  - Read the top of `PROGRESS.md`. Open the live site. Skim the latest commits.
  - Check for open issues labelled `incident`.
  - Read each new file in `docs/explainers/`. You will be asked about this in interviews.
  - Leave this item unticked; it never finishes.

## Added by the agent

- [ ] H10 · Make GitHub Actions jobs start
  - Every `ci` run on `main` fails within about 5 seconds and never gets a runner
    (run https://github.com/JASHD12/forecast-arena/actions/runs/43195868006, attempts 1
    and 2). The workflow file and action versions are valid; this pattern usually means an
    account-level block (billing / spending limit, a locked account, or Actions disabled
    or restricted in Settings > Actions > General).
  - Open the run in the browser: the annotation at the top of the job says the exact cause.
    Fix it there (the agent must not change repository or account settings).
  - Check: re-run the job; it should reach the "make check" step and go green.
  - Needed for T002, T074 (CI accessibility job), T083 (CI Docker job) and every live
    task (T030 onwards).
