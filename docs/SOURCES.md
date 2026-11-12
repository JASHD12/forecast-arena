# SOURCES.md - verified external facts

Every external fact the code relies on (API endpoints, parameters, publication times,
terms, licences, GitHub Action versions) is listed here with the official page it was
checked against and the date. Code must not rely on anything that is not in this table.

| Fact | Source URL | Date checked | Notes |
|---|---|---|---|
| `actions/checkout` current major is `v7` (latest v7.0.1) | https://github.com/actions/checkout (tags) | 2026-11-12 | read via `git ls-remote --tags` |
| `actions/setup-python` current major is `v7` (latest v7.1.0) | https://github.com/actions/setup-python (tags) | 2026-11-12 | same |
| `actions/configure-pages` `v6`, `actions/upload-pages-artifact` `v5`, `actions/deploy-pages` `v5` | https://github.com/actions (tags of each repo) | 2026-11-12 | for T030 |
| SMARD index `https://www.smard.de/app/chart_data/{filter}/{region}/index_{resolution}.json` returns `{"timestamps":[ms...]}`; chunk `.../{filter}_{region}_{resolution}_{ts}.json` returns `{"meta_data":{...},"series":[[ms, value or null]...]}` | https://github.com/bundesAPI/smard-api (openapi.yaml) and live calls | 2026-11-12 | no key needed |
| SMARD filter ids: 4169 price DE/LU, 410 load, 4359 residual load, 4067 wind onshore, 1225 wind offshore, 4068 solar | https://github.com/bundesAPI/smard-api (openapi.yaml) | 2026-11-12 | 4169 and 410 fetched live |
| SMARD chunks are weekly, start Monday 00:00 Europe/Berlin, hold 167/168/169 hourly values; future hours are `null` | live calls (weeks of 2026-03-23, 2026-10-19, 2026-11-09) | 2026-11-12 | fixtures in `tests/fixtures/smard/` |
| SMARD price history (4169, hour) starts 2018-10-01 Berlin | live index | 2026-11-12 | first timestamp 1538344800000 |
| SMARD hourly price = mean of the four 15-minute day-ahead prices (`quarterhour` resolution exists) | live comparison, week of 2026-11-02 | 2026-11-12 | e.g. 243.00 = mean(250.96, 245.99, 240.00, 235.05) |
| At 11:00 UTC on 2026-11-12 prices were published through 2026-11-12 only; delivery-day prices appear after the noon auction on D-1 | live call | 2026-11-12 | publication time to be logged daily (T023/T027) |
| SMARD data licence: CC BY 4.0, attribution "Bundesnetzagentur \| SMARD.de"; free use under § 111d EnWG. The page notes the licensing of wholesale prices is under review (HEDWIG procedure) | https://www.smard.de/home/datennutzung | 2026-11-12 | re-check monthly; risk noted in PROGRESS |
| `astral-sh/setup-uv` latest is v10.3.3 but moving major tags stop at `v7` | https://github.com/astral-sh/setup-uv (tags) | 2026-11-12 | not used: CI installs with pip from the lock file |

## Availability rules for historical data

Conservative rules for when a value counts as "available" to a forecaster (SPEC 7.0).
Filled in per source by T023, T040, T042, T044.

- **SMARD day-ahead price** for delivery day D: available from 14:00 Europe/Berlin on D-1
  (publication is around 13:00; one hour of margin). `arena.sources.smard.price_available_at`.
- **SMARD actuals** (load, generation) for Berlin day D: available two days after D ends.
  `arena.sources.smard.actuals_available_at`.
