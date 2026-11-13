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
- [x] H03 · Turn on GitHub Pages
  - Repository settings, Pages section: set the source to **GitHub Actions**.
  - Needed before the first live run (task T030).

## Needed later (the agent keeps working on other tasks meanwhile)

- [x] H04 · Choose an LLM provider and add the key
  - Pick a provider and an inexpensive model. **Set a monthly spending limit in the
    provider's console first.** The project's own caps (SPEC 9.4) are a second safety net.
  - In the repository's Actions secrets, add `ARENA_LLM_API_KEY`.
  - In the repository's Actions variables, add `ARENA_LLM_PROVIDER` (`anthropic` or
    `openai_compatible`), `ARENA_LLM_MODEL` (the exact model id), and, only for
    `openai_compatible`, `ARENA_LLM_BASE_URL`.
  - Never paste the key into a chat, a file, or a commit.
  - Needed for tasks T064, T065, T068.
- [x] H05 · Finish the Imprint and Privacy text (drafts are ready)
  - The agent drafted both at your request: `docs/legal/imprint.md` and
    `docs/legal/privacy.md`. Replace every `[FILL IN: ...]` (your name, postal address,
    e-mail, your state's data protection authority, the date).
  - Then copy them to `site_content/imprint.md` and `site_content/privacy.md` and push
    (or tell the agent the details and it does this). A file that still contains
    `[FILL IN` is never published; the page keeps saying "Pending".
  - Optional: `site_content/about.md` (who you are, a link to your profile).
  - Not legal advice: check the result, e.g. with a generator from a German data
    protection authority or a lawyer. Your address will be public on the site.
  - Done 2026-11-12: published from the details the owner gave (name, 35390 Gießen,
    e-mail, Hesse). Street and house number are still missing: see H14.
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

- [x] H10 · Make GitHub Actions jobs start
  - Every `ci` run on `main` fails within about 5 seconds and never gets a runner
    (run https://github.com/JASHD12/forecast-arena/actions/runs/43195868006, attempts 1
    and 2). The workflow file and action versions are valid; this pattern usually means an
    account-level block (billing / spending limit, a locked account, or Actions disabled
    or restricted in Settings > Actions > General).
  - Open the run in the browser: the annotation at the top of the job says the exact cause.
    Fix it there (the agent must not change repository or account settings).
  - Check: re-run the job; it should reach the "make check" step and go green.
  - Needed for T002, T074 (CI accessibility job), T083 (CI Docker job), T056 (weekly
    dry-run dispatch) and every live task (T030 onwards).
- [ ] H11 · Approve a workflow that opens a non-incident issue
  - T084 asks for a monthly workflow that opens an issue listing outdated dependency pins.
    The standing approvals in CLAUDE.md cover only issues labelled `incident`, so this is
    not pre-approved. If you agree, add a line to CLAUDE.md's standing approvals, e.g.
    "7. Committing a workflow that opens and updates one issue labelled `dependencies`
    listing outdated pins", and tick this item. Until then the report goes to the job
    summary of the `deps` workflow.
  - Needed for T084b.
- [ ] H12 · Crypto: confirm CoinGecko terms, add the key, approve the workflow secret
  - Read the CoinGecko API Terms of Service in your browser:
    https://www.coingecko.com/en/api_terms . Check that a free Demo key may be used to show
    daily prices and yes/no outcomes derived from them on a public, non-commercial research
    site with the credit "Data provided by CoinGecko". If it may not, tell the agent and
    crypto stays off. (The agent could not read this page: it answers 403 to scripts, and
    opening it in a headless browser was refused by the permission system. Refused
    command: `node terms.js .../cg/terms.txt` (Playwright `page.goto` of the terms page),
    wanted to read the terms before building, per AGENTS.md S7.)
  - Create a free CoinGecko Demo account and an API key (developer dashboard).
  - Add it as an Actions secret named `ARENA_COINGECKO_API_KEY` (Settings > Secrets and
    variables > Actions > New repository secret). Never paste it anywhere else.
  - Add to CLAUDE.md's standing approvals: "8. Committing workflows that pass the
    repository secret `ARENA_COINGECKO_API_KEY` to api.coingecko.com to fetch crypto
    prices." (Approval 2 covers only the LLM key.)
  - Tick this item. Needed for T045e.
- [x] H13 · Optional: switch the AI forecasters to a frontier model
  - Declined by the owner on 2026-11-12: the project must stay (almost) free. The AI
    forecasters stay on `claude-haiku-5-5`, and the daily token cap in the workflows is
    150000 (worst case about $1 a month). Recommended: set the monthly spending limit in
    the Anthropic console to $1-2 as a second safety net.
- [ ] H14 · Add your street and house number to the Imprint
  - German law (DDG section 5) expects a full postal address in the Impressum, not only
    postcode and city. Add the street line in `site_content/imprint.md` and
    `site_content/privacy.md` (above "35390 Gießen"), or tell the agent.
- [ ] H15 · Players' leaderboard: form, consent and privacy
  - Create a Google Form whose published response CSV has exactly the columns
    `code,question_id,probability,submitted_at,consent` (one row per answer; `code` is a
    random player code of 12-64 letters, digits, `_` or `-`; `consent` is `yes` when the
    consent box is ticked; `submitted_at` in ISO 8601 with a UTC offset). Do not ask for
    names or emails. Set the Actions variable `ARENA_PLAYERS_CSV_URL` to the CSV link
    (the `players` workflow reads it at 09:00 and 09:15 UTC; see `src/arena/forecasters/players.py`).
  - Write the consent text and extend `site_content/privacy.md` (a player code links a
    person to their forecasts; ledger entries cannot be erased). The agent drafts both on request.
  - Needed for T162.
- [ ] H16 · Recruiter page details
  - Put your degree, university, expected graduation, availability (hours/week, start
    date), languages and LinkedIn URL into `site_content/recruiters.md`, or tell the agent.
- [ ] H17 · Proofread the German page
  - Ask a German speaker to read `site_content/de.md` / the "Auf Deutsch" page once it
    exists (T141).
- [ ] H18 · Repository presentation on GitHub
  - Repo settings (owner only): description, website link, topics (e.g. forecasting,
    machine-learning, llm, mlops, rag), and pin the repo on your profile.
- [ ] H19 · Streamlit dashboard hosting (optional, free)
  - After T143: create a free Streamlit Community Cloud account, deploy
    `apps/dashboard/streamlit_app.py` from this repo, and set the Actions variable
    `ARENA_DASHBOARD_URL` to its address.
