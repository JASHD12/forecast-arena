# docs/project/HUMAN_TODO.md - things only you can do

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
  - Record your answer in `docs/project/DECISIONS.md`.

## Recurring

- [ ] H09 · Review (about five minutes a day at first, then twice a week)
  - Read the top of `docs/project/PROGRESS.md`. Open the live site. Skim the latest commits.
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
  - Short facts for the first screen go into `site_content/recruiter_facts.json`; every key
    is optional and anything missing is simply not shown (https links only):

```json
{"city": "Berlin", "availability": "20 h/week from 2027-01-04", "languages": "German B2, English C1",
 "linkedin": "https://www.linkedin.com/in/YOUR-NAME", "cv_url": "https://YOUR-HOST/cv.pdf",
 "email": "you@example.org"}
```

  - With `cv_url` the main button becomes "Download CV (PDF)"; otherwise LinkedIn or email.
- [ ] H17 · Proofread the German page
  - Ask a German speaker to read `site_content/de.md` / the "Auf Deutsch" page once it
    exists (T141).
- [ ] H18 · Repository presentation on GitHub
  - Repo settings (owner only): description, website link, topics (e.g. forecasting,
    machine-learning, llm, mlops, rag), and pin the repo on your profile.
  - Suggested description: "Live public benchmark: classical ML vs LLM agents forecasting tomorrow, with forecasts locked in a hash-chained ledger before the answer exists."
    Topics: forecasting, machine-learning, llm, llm-agents, mlops, time-series, data-science, python, github-actions, langgraph.
    Social preview (Settings > General > Social preview): upload `src/arena/site/static/og.png` (1200x630).
- [ ] H19 · Streamlit dashboard hosting (optional, free)
  - After T143: create a free Streamlit Community Cloud account, deploy
    `apps/dashboard/streamlit_app.py` from this repo, and set the Actions variable
    `ARENA_DASHBOARD_URL` to its address.
- [ ] H20 · External scheduler for the lock-critical jobs (optional, recommended)
  - Why: GitHub starts scheduled runs hours late on this repository (morning slot 00:15 started
    06:20 to 07:53 UTC; evening runs 22:52 to 04:00; players runs 17:31 to 19:37, after the
    lock). The lock is 09:30 UTC, so one very late day loses a batch.
  - What: in a free cron service (or on a machine you own), create these calls with a
    fine-grained token that has only "Actions: read and write" on this repository:
    - morning: every hour from 05:00 to 08:00 UTC, `workflow_dispatch` of `morning.yml`;
    - evening: once at 20:00 UTC, `workflow_dispatch` of `evening.yml`;
    - players (only after H15): once at 09:00 UTC, `workflow_dispatch` of `players.yml`.
  - Request for each (replace WORKFLOW and TOKEN; keep the token in the cron service):

```bash
curl -X POST -H "Authorization: Bearer TOKEN" -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/JASHD12/forecast-arena/actions/workflows/WORKFLOW.yml/dispatches \
  -d '{"ref":"main","inputs":{"dry_run":"false"}}'
```

  - Safe to repeat: a morning run after the batch is sealed does nothing, an evening run after
    questions exist does nothing, and a players row already written is never replaced.
  - Do not give the token to the agent (AGENTS.md S2, S3). Done when the Status page shows
    seven days of morning runs starting before 08:30 UTC.
- [ ] H21 · `main` now rejects direct pushes (found 2026-11-19)
  - What happened: `git push origin main` was refused: "Protected branch update failed ...
    Changes must be made through a pull request. 2 of 2 required status checks are expected."
    CLAUDE.md standing approval 1 allows pushing to `main`, so the branch rule was added
    after it. The agent did not retry or look for another route (AGENTS.md 2.4, S4, S10).
  - Refused command: `git push origin main` (commit "T200-T203 ...").
  - The work is on branch `claude/relaxed-bardeen-rmhyal` (pushed there, as the session requires).
  - You decide: (a) merge that branch yourself via a pull request (the agent does not merge), or
    (b) change the branch rule or the standing approval so the agent may push to `main` again.
    Until then Phase 12 tasks stay on the branch and CI/promote results for them are unconfirmed.
- [x] H22 · Decision: raise the LLM eval token cap for the larger ablation (T223b)
  - Why: the 24-question run of 2026-11-19 stopped at the default 60,000-token cap (about 14
    questions for two variants). A fair 24-question comparison of plain and context needs about
    100,000 tokens (roughly 2 US cents on the current model); adding the agent variants needs
    more.
  - Decision for you: allow the `max_tokens` input of `llm-eval.yml` to go up to 150,000 for one run?
    Reply yes (and the agent dispatches it from `main`) or no (T223b stays at the 60,000-token size).
  - Decided 2026-11-19 (yes, same model): one run with `max_tokens=100000` was dispatched from `main` (about 2 US cents). A free model was considered; the free options need an account or a much weaker local model.
- [x] H23 · Decision: one paid eval run of the agent variant (T223b)
  - What: dispatch `llm-eval.yml` from `main` with `agent=true`, `limit=12`, `max_tokens=200000`,
    plus the default plain and context variants. The agent makes up to 6 requests per question.
  - Estimated cost: 24 questions of plain plus context cost about 2 US cents; the agent is
    roughly 5 times heavier per question, so about 8 US cents at most for 12 questions (hard cap
    200,000 tokens).
  - Reply yes and the agent dispatches it, reads the result from the job log and commits it; or no.
  - Decided 2026-11-19 (yes): run 44611596780 dispatched from `main` (`agent=true`, 12 questions, 200,000-token cap); it cost about 1.8 US cents.
- [ ] H24 · Start the official record (this also switches the ensemble on)
  - You said yes on 2026-11-19 to a start on **2026-11-23**. The agent cannot do this: it is a repository
    setting (CLAUDE.md, S4).
  - Steps: on GitHub open the repository > Settings > Secrets and variables > Actions > tab "Variables".
    Edit `ARENA_OFFICIAL_START_NOT_BEFORE` if it exists, otherwise "New repository variable". Name:
    `ARENA_OFFICIAL_START_NOT_BEFORE`, value: `2026-11-23`. Save. Nothing else (no workflow edit).
    Do it before the morning run of 2026-11-22 so the daily clean-day check sees it.
  - What it does: the official record starts on the later of the day after five clean days in a row
    and 2026-11-23. From then the headline scores, findings and the leaderboard count only official days
    and nothing may be tuned on them (integrity rule I8). Rehearsal days stay visible but do not count.
  - Expected timeline: 17 and 18 Nov are clean; if 19 to 22 Nov are clean too (a successful morning run,
    the evening job done, health green, day sealed, no open incident), the record starts on 2026-11-23.
    The evening job runs late on GitHub (see H20), so one late evening can make a day unclean and move the
    start; the Status page ("Road to the official record") lists each day and its reason.
  - Ensemble: it registers itself when 60 questions answered by all five members (about 12 a day) have
    resolved in the official record, using the Monday cutoff, so its first forecasts are expected in the
    batch of Monday 2026-11-30. If the start slips, so does this by the same days.
  - How to check: Status page; `meta/official_start.json` on the `ledger` branch; then the "ensemble" row
    on the Leaderboard and `ensemble` forecasts in the ledger.
  - Undo: set the variable back to `2099-12-31` before the start is written. Once `meta/official_start.json`
    exists it is never changed.

