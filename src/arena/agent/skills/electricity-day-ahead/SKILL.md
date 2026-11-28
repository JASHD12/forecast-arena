---
name: electricity-day-ahead
description: German day-ahead electricity price questions (mean, max, min, spread, evening): what drives them and how often they resolve YES
topics: power
revision: 2
---

## What the data is

Questions are about the German/Luxembourg day-ahead auction price for one Europe/Berlin delivery day, 24 hourly prices in EUR/MWh. The context holds daily statistics of recent known days (`mean`, `max`, `min`, `spread`, `evening`) and the hourly prices of the latest day. Thresholds are medians of recent daily values, so a question is close to even by construction; the information is in the latest days, not in the base rate.

## What moves each statistic

- `mean`: follows wind and solar output, demand and gas prices. A windy, mild or holiday day lowers it; a calm, cold day raises it. It is strongly persistent day to day: yesterday's level is the best simple predictor.
- `max` and `evening`: set by the evening ramp when solar fades and demand peaks. They react to wind forecast and weekday demand.
- `min`: set by midday solar and low demand, so it falls on sunny weekends and holidays and can go negative. Negative prices are a real, recurring event in summer and on holidays.
- `spread`: highest minus lowest hour. It is large on days with strong solar and a steep evening ramp, small on flat, windy days. It is the noisiest statistic.
- Weekdays and holidays: weekends and public holidays have lower demand and lower prices.

## How to use the tools

1. Call `estimate_probability`: it is persistence with a normal error. It takes the latest stored day's value as the centre and the day-to-day swings in the window as the spread. It does not know the weekday pattern or the hourly shape of the latest day, and for `spread` and `min` it is rough.
2. Check what it cannot see. The estimate names the weekday of the latest day and of the target day: use the weekday tables below, because a Saturday or Sunday target after a weekday (or a Monday after a Sunday) is the commonest reason persistence is wrong. `up_vs_today` asks whether tomorrow's mean is above today's, so the share of YES by target weekday matters more there than any level.
3. Look at the latest day's hourly profile with `get_series` (`latest_hourly`) when the estimate is near 0.5: a day that already ended far from the threshold makes persistence reliable; a day that ended close to it does not.
4. Move away from the estimate when the weekday or the profile disagrees with it, or for news about outages, interconnector limits or a gas price shock, and say which.

## Base rates measured up to 2026-10-31

<!-- generated:power_rates -->
Source: backtest run `power-2025-11-01-2026-10-31-20261112T1356`, target days 2025-11-02 to 2026-10-31, computed by `scripts/skill_tables.py`.

| Template | Questions | Share YES | Same outcome as the day before |
|---|---|---|---|
| evening_gt | 364 | 0.56 | 0.71 |
| max_gt | 364 | 0.46 | 0.65 |
| mean_gt | 364 | 0.55 | 0.67 |
| min_lt | 364 | 0.34 | 0.75 |
| spread_gt | 364 | 0.53 | 0.65 |
| up_vs_today | 364 | 0.46 | 0.47 |

Share YES by weekday of the target day:

| Template | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| evening_gt | 0.60 | 0.73 | 0.67 | 0.63 | 0.60 | 0.37 | 0.33 |
| max_gt | 0.56 | 0.58 | 0.60 | 0.50 | 0.54 | 0.23 | 0.21 |
| mean_gt | 0.60 | 0.73 | 0.65 | 0.58 | 0.67 | 0.37 | 0.27 |
| min_lt | 0.21 | 0.25 | 0.25 | 0.27 | 0.27 | 0.52 | 0.58 |
| spread_gt | 0.67 | 0.56 | 0.52 | 0.65 | 0.52 | 0.44 | 0.35 |
| up_vs_today | 0.83 | 0.52 | 0.46 | 0.40 | 0.54 | 0.17 | 0.27 |
<!-- /generated:power_rates -->
