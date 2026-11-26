---
name: crypto-moves
description: crypto price questions (up or a big move of Bitcoin, Ethereum, Solana, XRP, BNB): random-walk direction, heavy tails and volatility clustering
topics: crypto
revision: 1
---

## What the data is

Questions ask whether a coin's daily price rises (`up`) or moves by more than a threshold in either direction (`bigmove`). The context holds recent daily closes. This is a forecasting exercise only; nothing here is a recommendation or advice.

## What to know

- Direction is close to a coin flip. Crypto prices are a near random walk day to day; momentum and news rarely give an edge a day ahead. For `up` questions the honest answer is close to 0.5, and a confident call needs a concrete reason.
- Size is more predictable than sign. Volatility clusters: turbulent days follow turbulent days, quiet follows quiet. Daily moves have heavy tails, so a threshold far above typical moves is rarely crossed but not impossible.
- Thresholds are set from recent volatility, so compare the threshold with the recent absolute daily moves. Weekends and thin markets can move more.
- No generated base-rate table is shown here: crypto questions began after 2026-10-31, and this skill only uses data before that date.

## How to use the tools

1. For `up`: stay close to 0.5, and move only for a concrete event.
2. For `bigmove`: use `get_series` to measure the recent absolute daily moves, compare them with the threshold, and use `calculate_probability` with a centre of zero and a spread taken from them (allow for heavy tails by not going below a few percent).
3. Do not read direction from headlines or social media; at most they hint that volatility may be higher than usual.
