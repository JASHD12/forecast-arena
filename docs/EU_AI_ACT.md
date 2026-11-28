# EU AI Act and GDPR: where this project stands (T392)

Written 2026-11-27. **This is my reading as the author, not legal advice.** It exists because German companies (Mittelstand, banks,
insurers, automotive) ask candidates whether they understand where an AI system sits under the EU AI Act (Regulation (EU) 2024/1689) and
the GDPR. The article texts below were read on 2026-11-27 (`docs/SOURCES.md`); the Act's application dates and guidance keep moving, so
check them before relying on this for a real deployment.

## What the system is

A public research benchmark. Every day it publishes yes/no probabilities about tomorrow (electricity prices, weather, Wikipedia
attention, exchange rates, crypto) from public data, scores them when the answer arrives, and shows the record on a static website.
Nothing is decided about a person, nothing is sold, and no one is asked to act on a forecast; the site says plainly that it is research and
not advice.

## Risk class: not high-risk; limited-risk transparency duties apply in spirit

The AI Act sorts AI systems by risk. High-risk systems are those used as a safety component of a regulated product or in the areas listed in
Annex III: for example biometrics, **safety components in the management and operation of critical digital infrastructure, road traffic or
the supply of water, gas, heating or electricity**, education, employment and worker management, access to essential services such as
credit scoring, law enforcement, migration and the administration of justice.

- **This project is not in any Annex III area.** It does not identify people, score people, rank applicants or decide access to a service.
- **The electricity topic is the one to watch.** The model forecasts a day-ahead price statistic for a public benchmark. It is not a safety
  component and nothing is controlled by it. A company that built the same model *into* grid operation as a safety component could fall
  under Annex III point 2 and would then need the high-risk obligations (risk management, data governance, logging, human oversight,
  accuracy and robustness testing, conformity assessment). That is the difference between a benchmark and a deployment, and it is the reason
  this document exists.
- **Transparency (Article 50).** Providers of AI systems meant to interact directly with people must make clear that they are AI (50(1)),
  and providers of systems that generate synthetic text must mark the output as artificially generated in a machine-readable way (50(2)).
  The project has no chat that pretends to be a person and publishes no synthetic media. Its model-written rationales are shown with an
  "AI" label and the line "AI-generated text, published unedited. It may be wrong and is not advice". The in-browser "Ask the Arena"
  chat answers from stored documents and says so. I have not added a machine-readable marker to the published rationales; a real
  deployment of such text would need one under 50(2).

## What the project already does that a company would also need

| Practice | Where |
|---|---|
| AI-generated text is labelled and its limits stated | question pages, the Methods page, the footer note |
| Every model call is logged (model, tokens, latency, tool calls), without prompt or answer text | `agent_traces/` in the ledger, the LLM page |
| No personal data is collected or shown; Wikipedia articles about people are excluded from the questions | `docs/SPEC.md` 7.3, the privacy page |
| No automated decision about any person | by construction: questions are about prices, weather, page views, rates |
| A failure is a recorded skip with a reason, never a substitute number | the ledger (`skip` records), integrity rule I6 |
| The record cannot be rewritten silently | append-only, hash-chained ledger; `arena ledger verify --git` |
| Hard cost and usage limits per day | `llm_max_tokens_per_day`, tested to equal the workflows |
| Pre-registered tests, negative results published | `lab/prereg/`, the Lab page |
| Human oversight of any change that matters | the owner approves launches, budgets and anything that changes the record |

## What a company deployment would add

A named owner and accountable role; a risk assessment and, if Annex III applies, a conformity assessment and registration; a data
protection impact assessment where personal data is involved; documented human oversight with the authority to override; monitoring after
deployment with incident reporting; supplier documentation for the general-purpose model it calls (the provider's obligations are not
the deployer's); retention and access rules for the logs; and staff who understand the system's limits.

## GDPR

The site sets no cookies, runs no analytics and loads nothing from third parties; hosting on GitHub Pages sends the visitor's IP address
to GitHub, which the privacy page states with its legal basis (Article 6(1)(f)). The benchmark data contain no personal data. The
controller's contact details are in the imprint and privacy pages as German law requires.

## Open questions I would ask a lawyer before a deployment

Whether a forecast that feeds an operational decision at a utility is a safety component; whether the model provider's transparency
duties cover the text a deployer republishes; and how long operational logs may be kept.
