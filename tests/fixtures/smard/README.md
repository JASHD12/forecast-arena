# SMARD fixtures

Real responses recorded on 2026-11-12 from `https://www.smard.de/app/chart_data/4169/DE/`
with the project User-Agent. Licence CC BY 4.0, source "Bundesnetzagentur | SMARD.de".
Files are stored unchanged.

| File | What | Why |
|---|---|---|
| `index_4169_DE_hour.json` | chunk index of the day-ahead price DE/LU (hourly) | index parsing, chunk selection |
| `4169_DE_hour_1766358000000.json` | week from Mon 2025-12-22 (Christmas holidays) | holiday golden tests |
| `4169_DE_hour_1774220400000.json` | week from Mon 2026-03-23: spring clock change, 167 hours | 23-hour day (2026-03-29) |
| `4169_DE_hour_1792360800000.json` | week from Mon 2026-10-19: autumn clock change, 169 hours | 25-hour day (2026-10-25) |
| `4169_DE_hour_1794178800000.json` | week from Mon 2026-11-09, recorded at 11:00 UTC on 2026-11-12: values up to 2026-11-12 23:00 Berlin, nulls after | null handling, "latest complete day" |

Also: every weekly chunk from Mon 2025-10-13 to Mon 2026-11-02 (`4169_DE_hour_<ts>.json`),
copied unchanged from the backfill cache (fetched 2026-11-12). They give the 60-day windows
for the power golden tests in `tests/fixtures/golden/power/`.
