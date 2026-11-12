# Demo: a 90-second screen recording

A script for the project owner to record. Times are approximate; speak the lines in
quotes in your own words. Record at 1280x720 or larger, browser zoom 110%.

| Time | Screen | What to say |
|---|---|---|
| 0:00-0:10 | Site home page | "Forecast Arena asks about 25 yes/no questions about tomorrow every morning: electricity prices, weather, Wikipedia attention and exchange rates. Several forecasters answer before the answer exists." |
| 0:10-0:22 | Home: latest questions table, then a question page | "Each question has a lock time at 09:30 UTC. Here are the probabilities from a base rate, a classical ML model, two LLMs and an LLM agent with tools. After the lock nothing can be added." |
| 0:22-0:35 | GitHub: the `ledger` branch, a `chain/batch/` file, the commit list | "Everything is appended to a public git branch and sealed with a hash chain. Anyone can run `arena ledger verify --git` and check that every forecast was committed before its lock." |
| 0:35-0:50 | Leaderboard page | "Scores are Brier and log scores with day-block bootstrap intervals. Until there are 30 official days the site says 'too early to tell', and a difference only counts when its interval excludes zero." |
| 0:50-1:02 | Calibration page | "Calibration matters as much as accuracy: when a forecaster says 30%, about 30% should happen. The diagonal is perfect calibration." |
| 1:02-1:15 | Findings page | "The four hypotheses were written down before any data, for example that the ML model beats every LLM on numeric questions. The page reports whichever way they fall." |
| 1:15-1:30 | `docs/models/power.md` in the repository, then the README | "Models were backtested on the same code as production: on a year of power data the ML model beat both baselines; on exchange rates nothing beat the base rate, as expected. The code, the rules and every decision are in the repository." |

Before recording: open the pages in tabs, close other windows, and check the site shows
today's batch. Do not show secrets, the Actions secrets page, or personal accounts.
