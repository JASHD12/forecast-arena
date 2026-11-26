---
name: weather-dwd-mosmix
description: German weather questions (heat, frost, rain, gusts, city duels) built on the DWD MOSMIX forecast: when to trust it and when to deviate
topics: weather
revision: 1
---

## What the data is

The context holds the stored DWD MOSMIX forecast for the target day (daily maximum and minimum temperature, precipitation total, highest hourly gust, plus the hourly series) and the last observed days for the station. MOSMIX is the official statistical forecast for station locations; it is the best single input you have for the next day.

## How reliable each variable is

- Temperature maximum and minimum: the most reliable. The error is small compared with typical thresholds, so the question is mostly whether the forecast value is above or below the threshold, with the error as a spread around it.
- Wind gusts: noticeably harder. Gusts depend on small-scale effects and fronts, so the spread is wide and thresholds near the forecast are close to coin flips.
- Precipitation: the hardest. A forecast total of zero is reliable for "dry day", but small totals near the "wet day" limit are uncertain, and showers can miss a single station.
- City duels (warmer than, wetter than): the difference of two forecasts; errors of the two stations add, so the spread is wider than for one city.

## How to use the tools

1. Call `estimate_probability`. For weather it applies a normal error around the stored forecast (the same rule the `ml` forecaster uses), so it is already a calibrated starting point. Do not recompute it differently without a reason.
2. The reasons to deviate are physical and specific: a front or a thunderstorm line passing close to the target day, fog or snow cover capping the temperature, or a forecast that changed sharply between the observed days and the forecast hour. If the context gives nothing like that, keep the estimate.
3. Do not search the news for weather: forecasts already contain what the news says.
4. When the forecast value sits very close to the threshold, the answer is near 0.5 whatever you do; accept that rather than forcing a direction.
