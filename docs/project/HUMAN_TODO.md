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
    "8. Committing a workflow that opens and updates one issue labelled `dependencies`
    listing outdated pins", and tick this item. Until then the report goes to the job
    summary of the `deps` workflow.
  - Needed for T084b. Exact steps: open `CLAUDE.md` on GitHub > pencil icon, add under "Standing approvals" the line
    `8. Committing a workflow that opens and updates one issue labelled \`dependencies\` listing outdated dependency pins.`
    Commit it (a PR is fine), tell the agent "H11 done", and tick this box. The agent may not add this line itself.
- [x] H12 · Crypto: confirm CoinGecko terms, add the key, approve the workflow secret  (2026-11-22: Demo key created and stored as the secret `ARENA_COINGECKO_API_KEY`; crypto switched on by default in the workflows at the owner's request. Still on you: read https://www.coingecko.com/en/api_terms once and keep the credit link; add standing approval 7 to CLAUDE.md (done by the agent at your instruction on 2026-11-22); if the repository variable `ARENA_DOMAINS` exists, edit it to end with `,crypto` or delete it so the new default applies.)
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
  - Add to CLAUDE.md's standing approvals: "7. Committing workflows that pass the
    repository secret `ARENA_COINGECKO_API_KEY` to api.coingecko.com to fetch crypto
    prices." (Approval 2 covers only the LLM key.)
  - Tick this item. Needed for T045e.
  - **EU/German rules check (agent's assessment of 2026-11-22; not legal advice).** Publishing free probability forecasts of daily
    crypto price moves, with no trading, no recommendation and no money involved, is not a regulated crypto-asset service under MiCA
    (Regulation (EU) 2023/1114: issuance, custody, exchange, advice and similar services need authorisation; a general forecast is not
    personalised advice) and not investment advice or a financial analysis under the WpHG, because crypto-assets are not financial
    instruments and nothing says "buy" or "sell". The rules that do apply: (1) MiCA's ban on market manipulation and misleading
    information, so never present a forecast as certain and state the track record honestly (the site already does); (2) no
    recommendations, no price targets as advice, no links to exchanges, no affiliate links, no donations tied to crypto content;
    (3) the "research project, not advice" notice on every page and the CoinGecko credit "Data provided by CoinGecko" with a link;
    (4) a complete Impressum (H14: street address) and the privacy page, as for the rest of the site; (5) no personal data.
    It changes if the project ever earns money from the crypto content, lets visitors stake anything, or gives individual
    recommendations: then get advice from a lawyer (IT or financial regulation) first. A one-hour consultation before going live is
    cheap insurance, but nothing here requires it.
  - **How to switch it on, in order:** (1) do the steps above (terms, key, secret, CLAUDE.md approval 7, tick H12); (2) tell the agent;
    (3) the agent adds the crypto notice and attribution checks, runs one dry run, and asks you to set the repository variable
    `ARENA_DOMAINS` to `power,weather,attention,markets,crypto` (Settings > Secrets and variables > Actions > Variables; the agent
    cannot change variables); (4) the first crypto questions appear in the next evening batch and start as rehearsal-only (outside
    the headline until 30 days). To stop at any time, set the variable back without `crypto`.
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
- [ ] H20 · External scheduler for the lock-critical jobs (optional, recommended; since 2026-11-24 the workflows also have many more scheduled slots, T329, which helps but cannot guarantee a start before the lock)
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
  - Progress (checked 2026-11-26): set up at cron-job.org (morning 05:00-08:30, evening 20:00 and 20:30, resolve every 3 hours at :20). The evening batch of 25 Nov was published by the 20:02 UTC dispatch (GitHub's own evening slots did not fire); GitHub's morning cron sealed the 25 and 26 Nov batches at 03:25 and 02:32 UTC, so the morning dispatches only record "already sealed". Two on-time mornings so far; tick this after about 2026-12-01 if it keeps up.
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
- [x] H24 · Start the official record (this also switches the ensemble on)
  - Owner reported on 2026-11-20 that `ARENA_OFFICIAL_START_NOT_BEFORE=2026-11-23` is set (the agent cannot read repository variables to confirm; the Status page "Road to the official record" shows the effect).
  - You said yes on 2026-11-19 to a start on **2026-11-23** and asked the agent on 2026-11-20 to set it. The agent
    cannot: `gh variable set` / the Actions variables API is refused by the sandbox proxy (HTTP 403, command
    `gh variable list`), and repository settings are outside its approvals (CLAUDE.md, S4). No other route was tried.
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
- [ ] H25 · Decision: wording of "supported" on boards that still say "too early to tell"
  - Today the leaderboard shows "supported: better than base_rate" in the Reading column even when the same board is
    labelled "too early to tell" (3 days, 30 questions). A first-time reader finds that contradictory.
  - Proposal: show "early sign: better than base_rate" while a board carries the "too early to tell" label, and
    "supported" only after the 30-day and 300-forecast gates. Statistics and the label rule stay as they are; only the
    word changes. SPEC section 10 (scoring and wording) is yours to change, so the agent has not touched it.
  - Reply yes (and the agent changes the wording and its tests) or no.

## Experiments lab (Phase 14, owner request 2026-11-21)

- [x] H26 · Run the QLoRA notebook on Colab (needed for T245)  (done 2026-11-22)
  - Open `notebooks/lab/qlora_qwen_forecast.ipynb` from the repository in Google Colab (File > Open notebook > GitHub, or the
    badge at the top of the notebook), Runtime > Change runtime type > T4 GPU, then Runtime > Run all. It takes about 30 to 60
    minutes. At the end it prints the SHA-256 of every output file and writes `outputs.zip`; download it.
  - You need a Google account. The agent cannot do this (AGENTS.md S2: no accounts, no signing up).
- [x] H27 · Approve the use of the Claude API key for non-forecast lab runs (needed for T247 and T252b)  (approved by the owner in chat, 2026-11-22: distillation labels and the LLM judge, within the US$2.00 lab budget; each run is still a manual dispatch)
  - CLAUDE.md standing approval 2 covers workflows that use `ARENA_LLM_API_KEY` to generate forecasts. The lab also wants two
    small paid runs: distillation labels (about US$0.35) and an LLM-as-judge run (about US$0.10), together at most US$2.00
    (`docs/project/LAB_BUDGET.md`). Reply yes to allow the agent to commit those two workflows; each is still a manual dispatch.
- [x] H28 · Upload the lab files as GitHub release assets (needed for T245)  (done 2026-11-22: release `lab-qlora-r1`)
  - After H26: GitHub > repository > Releases > Draft a new release, tag `lab-qlora-r1`, attach the files from `outputs.zip`
    (adapter, GGUF, logs; the training data is already in the repository, nothing to upload for it), publish.
    Paste the printed SHA-256 values and the release URL into the chat. The agent then pins them in code.
- [ ] H29 · Label 30 model rationales for the judge calibration (needed for T252b)
  - Easiest: open `lab/judge/label-cards.md` on GitHub (one readable card per item, nothing pre-filled, same 30 items as the sheet below) and
    note your three numbers per card. The raw table is `lab/judge/label-sheet.csv` (GitHub > the file > "Raw", or download it; 30 rationales, no forecaster names). For each row read the question, the data excerpt, the probability and the rationale, then give three whole numbers
    from 1 (poor) to 5 (excellent): **data_use** (are the numbers used correctly, none invented), **direction** (does the probability
    follow from the rationale), **hedging** (is the confidence right for the evidence). Do not guess the outcome.
  - The agent rated the same 30 cards itself (`lab/judge/ratings-agent.json`, card `docs/lab/judge-agent.md`); that is labelled as an LLM rater and does not replace your labels. If you still prefer not to label, say so and H29 stays open as "uncalibrated against humans".
  - Send me 30 lines in the chat, nothing else: `id,data_use,direction,hedging` (for example `9dcceff67a,4,5,3`). The agent writes
    the labels file and computes the agreement with the judge.
- [x] H30 · Decision: allow shadow forecasting (no longer needed: the lab techniques run live as normal forecasters, Phase 15)
  - A shadow forecaster writes real forecasts before the lock into a separate `shadow/` tree on the ledger that no board reads.
    It needs a small ledger-schema change. Reply yes to allow it, or no to keep both tasks as written proposals.

- [x] H31 · Approve one paid `llm-eval` run on the two frozen lab test sets (needed for T250)  (approved by the owner in chat, 2026-11-22; workflow `lab-routing.yml`, about US$0.15)
  - The routing study needs Claude's `llm_context` probabilities on all 276 test questions (`evals/golden/power-2026-10.jsonl` and
    `power-2026-11a.jsonl`). The existing workflow `llm-eval.yml` does it in one dispatch for about US$0.15 (recorded cost per call
    about US$0.0004, total lab budget limit US$2.00). Reply yes and the agent dispatches it once, with a token cap.
- [x] H32 · (owner decided 2026-11-22: calibrate on the GGUF (b) AND go live now with the pinned map; the workflow default is on, repository variable `ARENA_LLM_LOCAL_FT=0` switches it off) How the fine-tuned model goes live (needed for T271's go-live; you decided "whatever the result")
  - What the evidence says (`docs/lab/qlora-r1.md`, 276 test questions, 46 days; lower Brier is better):
    tuning helps (tuned 1.5B beats its untuned self, interval excludes zero) but the tuned 1.5B model is **worse than the plain base rate**
    and far from the `ml` champion; the 0.5B LoRA model is slightly better than the 1.5B QLoRA model. The 4-bit GGUF that would run live
    **missed the pre-registered parity limit** on 31 rows (Brier loss 0.0123, limit 0.005), probably because the Platt map was fitted on
    the Colab margins, not on the GGUF's.
  - Options, reply with a letter: (a) go live as pinned (Colab Platt map; expected a little worse than the card shows), flag `ARENA_LLM_LOCAL_FT=1`;
    (b) first calibrate on the GGUF itself: the agent adds a manual `lab-eval.yml` run that scores the validation and test sets with the GGUF
    on a free runner (a few hours, no API key), refits Platt on validation only and pins that (new version string); (c) do not go live yet.
    The agent recommends (b), then (a).
  - Also, if you ever set the repository variable `ARENA_LLM_MAX_TOKENS_PER_DAY`, change it to `300000`.

- [ ] H33 · Mac smoke run for the monthly retrain (needed for T281a), and later the launchd schedule
  - Needs your MacBook Air (M5, 16 GB). The agent cannot reach it from the cloud, so it will give you one script to run; send back the printed
    summary (memory, minutes, Brier). Run it on mains power, lid open. Do not schedule anything yet: the monthly schedule steps come after the smoke
    result in T281c.
- [ ] H34 · Phoenix documentation not reachable (T255b)
  - The agent could not read `https://arize.com/docs/phoenix/self-hosting/deployment-options/docker` (host does not resolve here), so it did not write a `make smoke-phoenix` target from memory. To unblock: allow the host `arize.com` for the session environment, or paste the page's image name, ports, OTLP traces path and licence into this item. Optional: nothing else depends on it.
- [x] H35 · Run the DPO notebook on Colab (needed for the DPO result, T299)  (done 2026-11-22: release `lab-dpo-r1`; no GGUF, the optional export cell failed on a notebook bug that is now fixed; rerun only if you want a DPO GGUF)
  - Ready: `notebooks/lab/dpo_qwen_forecast.ipynb` with the pre-registration `lab/prereg/dpo-forecast.md` (both on `main` after this PR is merged). Same steps as H26/H28: Colab, free T4, Runtime > Run all (about 1.5 to 2.5 hours), upload `outputs.zip` and the `.gguf` as release `lab-dpo-r1`, paste the release URL and the hashes (also `run_summary.json`). The export step stops with a clear error if the GGUF is not produced.
- [x] H36 · OK for the small paid runs of self-consistency (k=5) and the LLM judge (needed for T298)  (approved by the owner in chat, 2026-11-22)
  - Each is one capped manual workflow run within the US$2.00 lab budget (`docs/project/LAB_BUDGET.md`); the agent states the estimate and the cap before dispatching and waits for your yes.

- [ ] H37 · Optional: check the Terraform formatting on your own machine (T292)
  - The agent wanted to download the Terraform CLI from releases.hashicorp.com and run `terraform fmt -check -recursive infra/aws` locally before pushing; the permission system refused that action, so the agent did not retry or look for another route. The same check runs in CI (job `terraform`), which is enough; nothing is blocked. If you want to see it locally: install Terraform 1.17 from the official site and run `terraform fmt -check -recursive -diff` in `infra/aws`.

- [ ] H38 · Optional, only if you name a new topic: allow more data hosts so the agent can read their terms and record real responses (T302)
  - Blocked by the cloud environment's network allowlist (not by the sources): `www.umweltbundesamt.de`, `luftqualitaet.api.bund.dev` (air quality), `autobahn.api.bund.dev` (roadworks and traffic), `ec.europa.eu` (Eurostat), `www.bundesbank.de`. To allow them: claude.ai > Settings > the environment "forecast-arena" > Network access > add the hosts (exact names), then tell the agent. Nothing is blocked meanwhile. The owner said no to a pollen topic (2026-11-22); this item matters only if you name another topic. Crypto stays off until H12.
- [x] H39 · Run the distillation notebook on Colab (needed for the student model of T247; only after the label PR is merged)
  - Open `notebooks/lab/distill_qwen_forecast.ipynb` (File > Open notebook > GitHub, `JASHD12/forecast-arena`, branch `main`), Runtime > Change runtime type > **T4 GPU**, Runtime > **Run all** (about 1 to 2 hours). It trains the small model on the teacher's probabilities (`lab/data/distill-labels-v1.json`, already in the repository) and prints the SHA-256 of every output file. No GGUF is needed.
  - Download `outputs.zip`, unzip it, then GitHub > Releases > Draft a new release: tag `lab-distill-r1` (target `main`), tick pre-release, attach `scores_distill_1_5b.jsonl`, `run_summary.json`, `SHA256SUMS.json`, `train_log_distill_1_5b.json` (and the adapter file if you like), publish, and paste the release link into the chat. The agent then evaluates it against the teacher, the QLoRA model and the base rate.

- [ ] H40 · forecast-audit: owner-only steps (T324)
  - Contact and CV: add your CV link / LinkedIn / email to `site_content/recruiter_facts.json` (H16); the recruiter pages show a contact button only when you do.
  - Confirm the wording "Backend engineer targeting applied ML roles in Germany" on `recruiters-ml.html`, or tell the agent your real title.
  - GitHub About text and topics (repository settings, so the agent cannot): description "Offline tool that audits alert decisions from forecast probabilities against a baseline" and topics `forecasting`, `forecast-verification`, `python`, `energy`.
  - Discovery and pilot: run `docs/pilot/forecast-audit-pilot.md` with three volunteers and record the results.
  - Outreach choice (openmod or PyData Berlin) and whether to open an upstream issue (`docs/upstream/scores-candidate.md`): your decision; the agent posts nothing.
  - Tagging a `forecast-audit-v0.1` release from `docs/releases/forecast-audit-v0.1.md` is yours.

- [x] H41 · Optional: decide on the in-browser model tier for Ask the Arena (T316)
  - Today the chat answers from lookups and document search only; nothing is downloaded. A third tier could rephrase retrieved facts with a small model that runs in the visitor's browser (about 300 MB, loaded only after a click, from a third-party host). It needs your OK because it changes the privacy page and adds an outside download. Reply "yes tier 2" or leave it as is.
  - Answered yes 2026-11-23 (chat): tier 2 is built. Please test it once after the redeploy, in a recent desktop Chrome or Edge: open Ask the Arena, click "Load the in-browser model" (about 290 MB), ask "Who is winning?" and tell me what appears. The agent could not run it on a real WebGPU browser or reach jsDelivr, so this is the first real test.

- [ ] H42 · Put Forecast Arena on your GitHub profile (T326)
  - Work experience: added from your CV (2026-11-24) as `site_content/profile_cv.md` (four roles, wording copied from the CV, no phone or email). Edit that file and run `python scripts/profile_readme.py` to change it; `docs/profile/PROFILE_README.md` is the text to paste.
  - The agent cannot do this: the profile page is the README of a separate repository (`JASHD12/JASHD12`), and About text, topics and pinning are repository settings.
  - Profile README: GitHub > New repository, name exactly `JASHD12` (public), tick "Add a README file", create. Open its `README.md`, replace everything with the contents of `docs/profile/PROFILE_README.md` from this repository (regenerate first with `python scripts/profile_readme.py` after the latest merge), commit. It then shows on https://github.com/JASHD12.
  - Pin: your profile > "Customize your pins" > tick `forecast-arena` (and `JASHD12` is not needed).
  - About box of `forecast-arena` (gear icon next to "About"): description "Live public benchmark: classical ML vs LLM agents forecasting tomorrow, with forecasts locked in a hash-chained ledger before the answer exists." Website `https://jashd12.github.io/forecast-arena/`. Topics: forecasting, machine-learning, llm, llm-agents, mlops, time-series, data-science, python, github-actions, langgraph. Tick "Use the topics..." as you like; untick Releases/Packages if empty.
  - Check the wording "Specified and directed by me; implemented with AI coding agents" is how you want to describe your role; add your CV/LinkedIn/email to `site_content/recruiter_facts.json` (H16) so the profile shows a contact line.


- [x] H43 · Decide whether to try the committee again as `committee-r2` (T368): answered yes 2026-11-26 (chat); built, pre-registered, run pending the merge
  - Result of r1 (2026-11-26): it answered 37 of 90 questions because the skeptic's JSON broke (119 of 316 calls hit the 300-token output limit) and it was worse than `agent_skills` on those 37. `agent_skills` also missed its rule by a hair (cost 1.31x against 1.30x; the Brier interval includes zero). Nothing is live; see DECISIONS and `docs/lab/agent-committee.md`.
  - If yes: say "go for committee-r2" in chat. The agent then writes the fix as a new version (larger output budget for the scout and the skeptic, tolerant critique parsing), pre-registers it before any run, and asks you for the cost estimate of one more paid run (about US$0.15-0.25 for the committee arm; budget left after this run: US$0.50).
  - If no: tick this item and write "no"; the r1 result stays as the published outcome.

- [x] H44 · Decide whether Reddit may be used for the sentiment forecaster (T371b)
  - Why it is an owner decision: the Reddit Data API Terms (https://www.redditinc.com/policies/data-api-terms, read 2026-11-27) forbid "using User Content to train a machine learning or AI model without the express permission of rightsholders" (3.2), require deleting data not needed for the approved use, and forbid revenue from the API. The agent also could not read the rate limits (the Developer Documentation page only served a JavaScript check to its fetcher). Using the sentiment of posts as an input of a fitted model may fall under 3.2. The agent will not guess.
  - Recommended default: **no Reddit**. The forecaster runs on GDELT news tone alone (Part 1 as built). Reply "no Reddit" and T371b is closed.
  - If you want Reddit anyway: read https://www.reddit.com/wiki/api/ and the terms yourself, then reply "yes Reddit". You then need to: create a Reddit "script" app on your own account (https://www.reddit.com/prefs/apps) and accept the terms, add the repository secrets `ARENA_REDDIT_CLIENT_ID` and `ARENA_REDDIT_CLIENT_SECRET` (Settings > Secrets and variables > Actions; the agent never sees the values), and add standing approval 8 to `CLAUDE.md` for workflows that send them to Reddit's API. Until all of that is ticked the agent builds nothing that calls Reddit.
  - Answered 2026-11-27 (chat): **no Reddit, stay GDELT only.** T371b is closed; no Reddit secrets or CLAUDE.md approval 8 are needed. X is not used either (DECISIONS 2026-11-27).

- [ ] H45 · Approve the one paid run of the headline-label comparison (T375)
  - What it does: 500 current crypto headlines from GDELT are rated by a small open model (free, on the runner) and by Claude Haiku (paid), and the agreement is measured (`lab/prereg/sentiment-labels.md`). No headline is stored or shown. Estimated cost about 150,000 tokens, about US$0.03 to US$0.10; hard cap 400,000 tokens; lab budget left US$0.32.
  - It only helps the portfolio story (open model against LLM labeller); no forecaster needs it. Skipping it costs nothing.
  - To approve: reply "run the labels" in chat after the Part 1 pull request is merged. The agent then dispatches the workflow `lab-sentiment-labels` from `main` once.

- [ ] H46 · Choose the budget tier for the Part 2 paid evaluation (T381, `lab/prereg/analyst-and-calibration.md`)
  - The lab budget has US$0.32 left. Tier A (about US$0.13): `agent_analyst` and `llm_context` on the 90 November power questions. Tier B (about US$0.10 more): `llm_context` on the 186 October questions. Tier C (about US$0.40 more): `agent_quant`, `agent_skills` and `agent_analyst` on 120 weather and Wikipedia replay questions. The Part 1 label comparison (H45, at most about US$0.10) uses the same budget.
  - Reply with the tier and, for B or C, the new total lab budget (for example "tier A" or "tier A, B and C, lab budget US$2.50"). The agent then dispatches `llm-eval` from `main` once per tier, after the Part 2 pull request is merged. Nothing is spent before your reply.

- [ ] H47 · Hiring-impact actions only you can do (Part 3 of the hand-off plan)
  - Repository About (gear icon next to "About"): description "Live benchmark: AI agents vs a classical ML model forecasting tomorrow, every forecast locked before the answer exists"; website `https://jashd12.github.io/forecast-arena/`; topics `machine-learning`, `llm`, `ai-agents`, `forecasting`, `mlops`, `data-science`, `python`, `langgraph`, `time-series`. Pin the repository on your profile and publish the profile README (H42).
  - Fill `site_content/recruiter_facts.json` (H16): degree, university, semester, hours per week, start date, English and German level, city, LinkedIn, CV link. Without them the pages cannot show what a Werkstudent posting filters on (enrolment, hours, start). The agent never invents these.
  - Record the two-minute walkthrough from `docs/interview/walkthrough.md` and send the link.
  - CV: put the project in the first third of page one, three lines, one number, a link to the recruiter page; the same on LinkedIn (Featured).
  - Applying: send the recruiter-page link with two sentences tailored to each posting, apply in volume to Werkstudent roles, and ask for referrals. A project helps an application; it does not replace one.
  - Proofread the German page (`de.html`, H17); until then it is marked as not proofread.
  - Refresh the numbers when you want fresh ones: pull the `ledger` branch, then run `python scripts/standings_snapshot.py <ledger dir>`, `python scripts/readme_sections.py`, `python scripts/model_cards.py`, `python scripts/interview_numbers.py` and `python scripts/case_study_pdf.py <ledger dir>` (or ask the agent).

- [ ] H48 · Publish the new GitHub profile (T396; after the PR is merged)
  - Profile README: regenerate nothing; copy `docs/profile/PROFILE_README.md` from `main` into `JASHD12/JASHD12/README.md` and commit (the agent cannot push to that repository).
  - github.com/settings/profile: Bio `Software engineer · M.Sc. Data Science @ Uni Marburg · Python, Azure, Kafka, ML & LLM evaluation · building Forecast Arena`; Location `Gießen, Germany`; Website `https://jashd12.github.io/forecast-arena/`; public email: the one on your CV.
  - Pins ("Customize your pins"): `forecast-arena` and `datapilot`; leave the 2022 repos unpinned.
  - Repo About: `forecast-arena` description `Live benchmark: LLM agents vs a classical ML model forecasting tomorrow (electricity, weather, crypto); every forecast locked before the answer exists`, website the live site, topics `machine-learning, forecasting, llm, ai-agents, time-series, energy, mlops, python, github-actions`. `datapilot` description `Text classification and multilingual retrieval workbench: TF-IDF vs E5 embeddings, chronological evaluation`, topics `nlp, machine-learning, retrieval, python`.
  - Optional: archive or describe TODOLIST, CHAT-ROOMS, Expense-Tracker, Crypto_Feed, QuizCMS, Driver-Drowsiness-Detection, Share-Memories (reversible).
  - CV link: your CV PDF contains your phone number. If you want a "CV (PDF)" link, host a copy without it (for example in `JASHD12/JASHD12`) and tell the agent its https URL for `cv_url` in `site_content/recruiter_facts.json`.
  - Check your DataPilot numbers on the live profile (6,548 reviews, macro-F1 0.6475): the new text leaves them out until they are verified in that repository.

- [ ] H49 · Launch `agent_hybrid` (T398; after the PR is merged)
  - Agent first (no action from you): a dry run at about 00:05 UTC (`gh workflow run morning.yml --ref main -f dry_run=true -f only=agent_hybrid`; the run will look red because the health check reads the unsealed real checkout, the agent reads the morning step's log line), and a headroom check of the last three days' token and request use on the `ledger` branch. The agent writes the result under this item.
  - You, once the agent says the headroom is enough: GitHub > repository > Settings > Secrets and variables > Actions > Variables > New repository variable, name `ARENA_AGENT_HYBRID`, value `1`. To undo it, set the value to `0`.
  - The agent checks the next morning: coverage, skips, parse failures, no `budget_exhausted` skips on the core forecasters, the version string.

- [ ] H50 · Optional: archive GDELT news aggregates for a fresh-days test of `sentiment` (T402)
  - Only if you want the news-tone idea tested again: GitHub > repository > Settings > Secrets and variables > Actions > Variables > New repository variable, name `ARENA_SENTIMENT`, value `1`. The morning job then archives daily tone and article counts of the five coins in the crypto context (aggregate numbers only, no article text, no secret). To stop, set it to `0`.
  - About 60 days of archive are needed before a re-test is worth running; the agent then writes a new pre-registration first. The forecaster itself stays off (it failed its pre-registered rule, and the lag note explains why).

