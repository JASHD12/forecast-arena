# Two-minute walkthrough: script (T391)

For the owner to record (screen capture with a voice-over, English). About 280 words, two minutes. Open the live site's home page first.
Nothing here is a claim the site does not already show; read the numbers off the screen, do not memorise them.

| Time | On screen | Say |
|---|---|---|
| 0:00 | Home page, standings | "This is Forecast Arena: a live benchmark where an AI agent and a classical ML model forecast tomorrow. Every forecast is locked before the answer exists." |
| 0:15 | Standings, the "too early to tell" label | "These are the official standings. I show the interval, not just a rank, and the page says 'too early to tell' until the data can decide. That is on purpose." |
| 0:35 | Leaderboard, per-topic boards | "Per topic, the ML model is ahead on weather and electricity, and the AI agent is level with it on Wikipedia, which is news-driven. The ML model turns the weather forecast into a probability with an error model; the language models only read the numbers." |
| 1:00 | Ledger / guide page, `arena ledger verify` | "Every forecast goes into an append-only, hash-chained ledger. One command checks that nothing was written after its question locked." |
| 1:20 | Lab page | "I also test ideas and publish the ones that fail: a committee of agents, a fine-tuned small model, news tone for crypto. Each was pre-registered and each lost or added nothing." |
| 1:45 | Recruiter page | "The code is on GitHub, with CI, Docker and Kubernetes. The recruiter page has a one-page case study. I built this to show that I can ship, measure honestly and say what did not work." |
| 2:00 | End card | "Thank you." |

Recording notes: 1080p, browser at 1366 wide, dark or light theme as you prefer, no personal data on screen. Save the file and add its link to
`site_content/recruiter_facts.json` as `walkthrough_url` (a new optional key is a small code change; ask the agent) or to the profile README.
