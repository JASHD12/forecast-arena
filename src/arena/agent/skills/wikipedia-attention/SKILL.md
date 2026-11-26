---
name: wikipedia-attention
description: Wikipedia pageview questions (will an article get at least N views tomorrow): dynamics, thresholds and when news or the article text helps
topics: attention
revision: 1
---

## What the data is

Each question names one German or English Wikipedia article and a threshold of daily views for the target day. The context holds the article's recent daily views. Thresholds are set from the article's own recent level, so the question asks whether tomorrow will be higher or lower than that level.

## What moves pageviews

- Decay: after a spike (a death, a film release, a match, an announcement) views fall back quickly over a few days. If the last days are far above the older level, the base case is a decline, and a threshold near the spike level is likely NO.
- Weekday cycle: many articles have weekday and weekend patterns (school and work topics versus entertainment and sport).
- Scheduled events: a premiere, a TV broadcast, an election, a match or an anniversary on the target day raises views. Check whether such an event falls on the target day.
- Slow articles: stable reference articles move little; for them the recent average is a strong predictor.

## How to use the tools

1. Call `estimate_probability` if it offers one; for this topic it usually reports that no reference model exists. Then use `get_series` to look at the last days and compare the threshold with the recent level and the trend.
2. Use `search_news` or `wikipedia_summary` when the article is about a current event or a person in the news: a recent event can explain a spike that has not yet decayed, or a scheduled one that is about to start.
3. The `ml` forecaster already models the view trajectory. If `get_ml_forecast` is available, treat it as the anchor and move only for an event it cannot know about.
4. Spikes and events are the main source of surprises; when evidence points clearly to an event on the target day, be willing to be confident.
