# Per-forecast explanations (backtest, not the live record)

Model `power-gbq-r1-2026-11-01` (trained with reduced settings for this illustration) replayed on 2026-11-10. For each question the input features are replaced one group at a time by their typical value (median of the last week of inputs); the change in the probability, in percentage points, is the effect. The three largest are shown. This describes what the model reacts to, not why the market moves.

**Will the German/Luxembourg day-ahead electricity price for Wednesday 11 November 2026 (Europe/Berlin delivery day, 24 hours) have a daily mean price above 227 EUR/MWh?**  P(YES) = 77.5%

- mean: yesterday: +1.4 points
- evening: yesterday: +0.4 points
- weekday: +0.0 points

**Will the German/Luxembourg day-ahead electricity price for Wednesday 11 November 2026 (Europe/Berlin delivery day, 24 hours) have a highest hourly price above 311 EUR/MWh?**  P(YES) = 78.8%

- spread: yesterday: +1.0 points
- mean: yesterday: +0.5 points
- evening: yesterday: +0.2 points

**Will the German/Luxembourg day-ahead electricity price for Wednesday 11 November 2026 (Europe/Berlin delivery day, 24 hours) have a lowest hourly price below 72 EUR/MWh?**  P(YES) = 21.4%

- mean: last 7 days, spread: +0.3 points
- evening: last 7 days, spread: +0.1 points
- weekday: +0.0 points
