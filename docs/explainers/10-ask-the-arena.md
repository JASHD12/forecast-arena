# 10 - Ask the Arena: how the chat works, why it is built this way, what was left out

A page, `ask.html`, where a visitor asks about the arena's published forecasts, results and methods.
It runs in the browser from one data file, `chat/pack.json`; it needs no server and no key. Design record: `docs/project/DECISIONS.md` (2026-11-22).

## What was asked, and what was built

The first request was a chatbot that predicts any question, such as a stock price on a given day. That was declined: a stock is a financial instrument, an on-demand prediction breaks the rule that a forecast exists before its answer (I1), and a public language-model endpoint needs a server and an exposed key. The owner chose instead a chat about the arena's own record, free in the browser, which declines what is not forecast and shows the nearest published question.

## How an answer is made

1. **Guard.** Finance, advice and personal-data questions get a fixed refusal ("research project, not advice").
2. **Tier 0, lookup.** Slots (date, topic, threshold) are matched to a published question; boards and the status line are read directly. A wrong threshold is not an exact match.
3. **Tier 1, documents.** BM25 over chunks of the SPEC, methods, explainers and lab cards; the answer is the best-matching sentences, cited by chunk id. If fewer than half of the question's content words are covered, it says it does not know.
4. **Decline.** "There is no locked forecast for that", plus the nearest published questions.
5. **Which forecaster leads.** If the ML forecast is at least 15 points from 50%, it leads; otherwise the forecaster with the best record on that topic (at least 20 questions), otherwise the base rate. All locked forecasts are listed. This rule comes from the routing study and is labelled a hypothesis.

## Why it is built this way

- No language model writes the text, so nothing can be invented: every number is copied from the pack (checked by the evaluation).
- The pack contains only published data and is capped at 1.5 MB.
- The tiers are ordered by cost and risk: a lookup is exact, documents are quoted, everything else declines.
- The orchestrator is strict TypeScript with no dependencies; its BM25 scores equal the Python index (test).

## What was rejected

- A model behind an API key (cost, abuse, S8). - A server. - Browser embeddings (size).

## Tier 2 (added 2026-11-23)

An opt-in button loads Qwen2.5-0.5B through WebLLM (about 290 MB, after a click, WebGPU browsers only). The model never answers questions; it only rewords the facts of a lookup or document answer. The page rejects its wording if any number is not in those facts, and the library is refused unless its SHA-256 matches. A page-specific CSP allows the download hosts; no other page does. It is tested with a fake engine; a real-browser test is the owner's.

## Honest limits

The golden questions were written by the project, not by visitors; two method questions are missed because the document search has no stemming; the fixture pack has one topic. Details are on the card `docs/lab/ask-arena.md`.

## Ten questions an interviewer may ask

1. Why not let a model answer? Cost, abuse and invented facts; extraction cannot invent.
2. Why refuse stock questions? Regulation and the forecast-before-truth rule; the project forecasts only what it publishes.
3. How do you stop invented numbers? Answers are assembled from pack values; the evaluation checks that every number occurs in the pack or the question.
4. Why BM25 and not embeddings? Size, no download, and it is enough for short documents; parity with Python is tested.
5. How does it choose which forecaster to show? By difficulty: decisive ML first, else the topic's best record; a hypothesis.
6. What happens on an unforecast question? It declines and shows the nearest published questions.
7. How is it tested? Node tests, a golden set with generated lookups, and a browser test over http with no outside request.
8. What does it not do? New predictions, advice, memory of earlier turns.
9. What does tier 2 add? Plain-language rewording only, behind a grounding check that drops any wording with a number not in the facts; opt-in because of the 290 MB download and three outside hosts.
10. How do you know the refusal list is complete? You do not; it is a rule list with tests, reported as a rate, and the page says it is not advice.
