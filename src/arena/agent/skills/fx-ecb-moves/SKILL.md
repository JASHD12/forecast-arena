---
name: fx-ecb-moves
description: ECB euro reference rate questions (direction and big moves of EUR/USD and EUR/JPY): near-random-walk behaviour and how thresholds relate to volatility
topics: markets
revision: 1
---

## What the data is

Questions are about the next ECB euro foreign exchange reference rate for the dollar or the yen: whether the rate rises (`up`) or whether the absolute move exceeds a threshold (`absmove_gt`). The context holds the recent reference rates.

## What to know

- Direction is close to a coin flip. Day-to-day changes in major exchange rates are nearly unpredictable from past prices, so for `up` questions the honest answer is near 0.5 and a confident forecast needs a concrete reason. Do not read direction from news headlines: the market has already priced them.
- The size of the move is more predictable than its sign. Volatility clusters: after large moves, large moves tend to follow; in calm spells, small ones. The threshold of an `absmove_gt` question is set from recent move sizes, so compare it with the last days' absolute moves.
- Events with scheduled information (central bank meetings, employment data) raise the chance of a big move on that day; a quiet calendar lowers it.

## How to use the tools

1. For `up`: start at about 0.5 (the base rate and persistence below are the reference). Move only for a concrete, scheduled reason, and then not far.
2. For `absmove_gt`: use `get_series` to compute recent absolute moves, compare them with the threshold, and use `calculate_probability` with a centre of zero and a spread taken from recent moves if you want a number.
3. Stay away from the extremes: a single surprise move is common.

## Base rates measured up to 2026-10-31

<!-- generated:markets_rates -->
Source: backtest run `markets-2024-11-01-2026-10-31-20261112T1423`, target days 2024-11-04 to 2026-10-30, computed by `scripts/skill_tables.py`.

| Template | Pair | Questions | Share YES | Same outcome as the day before |
|---|---|---|---|---|
| absmove_gt | EUR_JPY | 508 | 0.48 | 0.51 |
| absmove_gt | EUR_USD | 508 | 0.49 | 0.52 |
| up | EUR_JPY | 508 | 0.56 | 0.47 |
| up | EUR_USD | 508 | 0.46 | 0.51 |
<!-- /generated:markets_rates -->
