# COMPLIANCE.md - EU and German rules: where the project stands

Written by the coding agent on 2026-11-12 at the owner's request ("follow all rules").
This is an engineering checklist, **not legal advice**. Where a rule needs a person's
identity or a legal judgement, it is the owner's job (AGENTS.md: the agent must not invent
legal text). Status: done = built and tested in code; owner = needs the owner; watch = fine
now, matters if the project changes.

| Area | Rule (short) | Status | What the project does / what is left |
|---|---|---|---|
| Provider identification | German Digital Services Act (DDG) section 5: websites offered "geschäftsmäßig" need an Impressum that is easy to find | **owner** | An Imprint page is linked from every page. It shows "Pending" until the owner writes `site_content/imprint.md` (name, postal address, e-mail). Whether a non-commercial research site needs one is the owner's call; having one is the safe default. HUMAN_TODO H05. |
| Privacy notice | GDPR Art. 13: tell visitors who is responsible, what is processed, why, legal basis, recipients, retention, their rights, the right to complain | **owner** (facts done) | The Privacy page states the technical facts (no cookies, no trackers, no third-party requests, no forms; GitHub Pages logs visitor IP addresses for security). The owner adds the controller identity, contact and rights text in `site_content/privacy.md`. H05. |
| Cookies and device storage | German TDDDG section 25 / ePrivacy: storing or reading information on a visitor's device needs consent unless strictly necessary | done | The site sets no cookies and uses no local or session storage, so no consent banner is needed. Since T130/T137 one self-hosted script (`static/app.js`: the game, sortable tables, the lock countdown, archive search and a theme toggle) runs in memory only on every page; a unit test fails if it ever mentions storage, cookies, `fetch` or an external URL, if a page has an inline script or event handler, or if a script comes from anywhere but `static/`. Every page carries a Content-Security-Policy (`script-src 'self'`). |
| Third-party requests | GDPR: loading e.g. Google Fonts sends the visitor's IP to a third party without consent (LG München I, 20 Jan 2022, 3 O 17493/20) | done | No external fonts, scripts, images or embeds; a unit test checks every page and the stylesheet. Links are plain links; `referrer` is set to `no-referrer`. |
| Hosting | GDPR: hosting provider as recipient; possible transfer to the USA | **owner** | GitHub Pages (GitHub, Inc.) logs IP addresses (GitHub docs, "Data collection"). The owner's privacy notice should name GitHub as recipient and point to the GitHub Privacy Statement; the owner should check the transfer basis GitHub states (e.g. EU-US Data Privacy Framework). |
| Personal data in content | GDPR data minimisation; S12 | done | No personal data in questions, forecasts or the ledger. Wikipedia articles about people are excluded (Wikidata "instance of: human" check, fail-closed). News tool stores headline, outlet, URL and time only. |
| Data licences | CC BY 4.0 (SMARD, DWD): credit and indicate changes; ECB: cite the source; Wikimedia: attribution; CoinGecko: "Data provided by CoinGecko" with a link | done | Credits on every page, with "computed by this project" where values are derived. CoinGecko credit with link appears once crypto questions exist. |
| AI transparency | EU AI Act Art. 50: people should be told when text is AI-generated, especially published text on matters of public interest (obligations apply from 2 Aug 2026) | done | Every page has an "AI disclosure"; AI forecasters carry an "AI" label; rationales say "AI-generated text, published unedited"; each forecast shows the model version. |
| Investment recommendations | EU Market Abuse Regulation Art. 20 (shares and other financial instruments) | done / watch | No questions about shares, indices or other financial instruments. Exchange rates are ECB reference rates. Every page says "not advice". Adding stocks would need a licence and legal advice first (docs/project/DECISIONS.md). |
| Crypto | MiCA (Regulation (EU) 2023/1114) has its own market-abuse rules for crypto-assets | watch | The crypto domain publishes probabilities of daily moves for research, with no trading, no recommendation and a clear disclaimer. It is not live until H12. If the project ever earns money or gives recommendations, get legal advice. |
| Accessibility | WCAG 2.x; the European Accessibility Act targets certain commercial services | done (voluntary) | axe-core check on every page, desktop light and phone dark, in CI: 0 serious or critical violations. Charts and bars always print their numbers. |
| Human panel | GDPR consent, information, right to erasure (Art. 17) vs. an append-only public ledger | **owner** before H06 | Members must agree in writing before joining. Because the ledger is append-only and public, entries cannot be deleted later; members must be told this. Proposal in docs/project/DECISIONS.md: publish the panel only as an aggregate (median), not per pseudonym. |
| Secrets | Security of keys | done | Keys only as GitHub Actions secrets; the CoinGecko key is sent in a header, never in URLs, logs or the ledger. |

## What the owner should do (in this order)

1. Write `site_content/imprint.md` (H05): name, postal address, e-mail. The site picks it up
   on the next build.
2. Write `site_content/privacy.md` (H05): who is responsible and how to reach them, that
   GitHub Pages logs IP addresses (recipient GitHub, Inc., with a link to its privacy
   statement and transfer basis), the legal basis you rely on, retention as stated by
   GitHub, visitors' rights (access, erasure, objection, complaint to a data-protection
   authority). A generator from a German data-protection authority or a lawyer can help.
3. Before the human panel: decide the panel publication form (aggregate only is safest)
   and write the consent text.
