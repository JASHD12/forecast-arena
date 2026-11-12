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
| Bright Sky `GET https://api.brightsky.dev/weather` (`dwd_station_id`, `date`, `last_date` inclusive, `tz`, `units=dwd`) returns `{"weather":[...],"sources":[...]}`; no key; free for all purposes; DWD terms apply | https://api.brightsky.dev/openapi.json, https://brightsky.dev/docs/ | 2026-11-12 | live calls for 4 stations |
| Bright Sky `temperature` = air temperature at the timestamp (2 m); `precipitation` = total of the previous 60 minutes (mm); `fallback_source_ids` marks values from another station; source `observation_type` is `historical`/`current` (observations) or `forecast` (DWD MOSMIX) | https://api.brightsky.dev/openapi.json | 2026-11-12 | |
| Bright Sky data come from opendata.dwd.de: historical CDC hourly observations, current-day POI reports, MOSMIX local forecasts | https://api.brightsky.dev/openapi.json (description) | 2026-11-12 | historical obs of 11 Nov were published by 11:00 UTC on 12 Nov |
| DWD open data (spatial data and HVD) may be re-used under CC BY 4.0 with the source acknowledged | https://www.dwd.de/EN/service/legal_notice/legal_notice.html | 2026-11-12 | attribution used: "Deutscher Wetterdienst (DWD), via Bright Sky" |
| Stations (DWD id): Frankfurt/Main 01420, Berlin-Dahlem (FU) 00403, Hamburg-Fuhlsbüttel 01975, München-Flughafen 01262; each has hourly observations since 2010/2011 and a MOSMIX forecast point | https://api.brightsky.dev/sources?dwd_station_id=... | 2026-11-12 | München-Stadt 03379 has no MOSMIX point; Berlin-Tempelhof has a 2022 gap |
| Open-Meteo free API: non-commercial only, < 10,000 calls/day, 5,000/hour, 600/minute, per IP; data CC BY 4.0 | https://open-meteo.com/en/terms | 2026-11-12 | from this sandbox the shared IP had already exhausted the daily quota (HTTP 429) |
| Wikimedia top list `https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{project}/all-access/{YYYY}/{MM}/{DD}` returns up to 1000 articles (`article`, `views`, `rank`); 404 before publication | live calls | 2026-11-12 | de list of 11 Nov had 997 entries; lists of 11 Nov were published by 11:30 UTC on 12 Nov |
| Wikimedia per-article `.../per-article/{project}/all-access/user/{title}/daily/{YYYYMMDD}/{YYYYMMDD}`; title percent-encoded incl. `/` (`AC%2FDC`); 404 when no data | live calls | 2026-11-12 | |
| Wikimedia API rate limits (new in 2026): 200 req/min for unauthenticated clients with a compliant User-Agent (contact URL or e-mail), 10 req/min unidentified; at most 3 concurrent requests; honour Retry-After on 429/503 | https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits | 2026-11-12 | 429 with `retry-after: 2..11` seen from this shared sandbox IP |
| Scripts must send an informative User-Agent with contact information | https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy | 2026-11-12 | ours: `ForecastArena/0.1 (+<repo URL>; <ARENA_CONTACT or repo URL>)` |
| Wikidata `https://www.wikidata.org/w/api.php?action=wbgetentities&sites=dewiki&titles=a|b&props=claims|sitelinks` gives P31; human = Q5; missing titles are flagged `missing` | live call | 2026-11-12 | up to 50 titles per call |
| Licence of pageview statistics: **not verified** (the API documentation page renders with JavaScript only) | https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/ | 2026-11-12 | site attribution names the source without claiming a licence; re-check |
| ECB Data Portal `https://data-api.ecb.europa.eu/service/data/EXR/D.USD+JPY.EUR.SP00.A?format=csvdata&startPeriod=...&detail=dataonly` returns CSV (`TIME_PERIOD`, `OBS_VALUE`, ...); no key | live calls | 2026-11-12 | fixing of 11 Nov had Last-Modified 14:57 UTC |
| Reference rates are updated around 16:00 CET on working days except TARGET closing days; concertation around 14:10 CET; four decimals | https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html | 2026-11-12 | |
| TARGET closing days = 1 Jan, Good Friday, Easter Monday, 1 May, 25 and 26 Dec: matches every weekday of the EUR/USD series 2019-01-01 to 2026-11-11 (0 mismatches) | the data above | 2026-11-12 | the TARGET calendar page is a PDF |
| ECB website terms: free use; the ECB must be cited as source; modifications (e.g. computed growth rates) must be stated | https://www.ecb.europa.eu/home/disclaimer/html/index.en.html | 2026-11-12 | site says "log returns computed by Forecast Arena" |
| Anthropic Messages API via the official Python SDK `anthropic` 2.8.0 (`client.messages.create(model, max_tokens, system, messages, tools)`); content blocks `text`/`thinking`/`tool_use`; `tool_result` blocks with `tool_use_id`, `is_error`; `stop_reason` end_turn/max_tokens/stop_sequence/tool_use/pause_turn/refusal; `usage.input_tokens/output_tokens`; current models reject `temperature`/`top_p`/`top_k` (400 on API version 2026-10-21); forced `tool_choice` any/tool rejected on the newest models | claude-api skill reference (cached 2026-11-03) and the installed SDK | 2026-11-12 | SDK 2.8.0 sends `anthropic-version: 2026-10-21` and the key as `Authorization: Bearer` (observed with a mock transport) |
| OpenAI chat completions: `POST {base}/chat/completions`; `max_completion_tokens` (`max_tokens` deprecated); `temperature` 0-2; function tools `{type: function, function: {name, description, parameters}}`; tool messages need `tool_call_id`; response `choices[0].message.tool_calls[].function.arguments` is a JSON string; `finish_reason` stop/length/content_filter/tool_calls; `usage.prompt_tokens/completion_tokens` | https://github.com/openai/openai-openapi (openapi.json) | 2026-11-12 | |
| German nationwide public holidays (New Year, Good Friday, Easter Monday, 1 May, Ascension, Whit Monday, 3 Oct, 25/26 Dec) used as a model feature | statutory list; **not checked against an online page** in this session | 2026-11-12 | feature only; affects no question or resolution |
| `astral-sh/setup-uv` latest is v10.3.3 but moving major tags stop at `v7` | https://github.com/astral-sh/setup-uv (tags) | 2026-11-12 | not used: CI installs with pip from the lock file |

## Availability rules for historical data

Conservative rules for when a value counts as "available" to a forecaster (SPEC 7.0).
Filled in per source by T023, T040, T042, T044.

- **SMARD day-ahead price** for delivery day D: available from 14:00 Europe/Berlin on D-1
  (publication is around 13:00; one hour of margin). `arena.sources.smard.price_available_at`.
- **SMARD actuals** (load, generation) for Berlin day D: available two days after D ends.
  `arena.sources.smard.actuals_available_at`.
- **DWD hourly observations** (Bright Sky): available 6 hours after their timestamp.
  `arena.sources.brightsky.observation_available_at`.
- **DWD MOSMIX forecasts**: no history is available through Bright Sky; the morning job
  snapshots the forecast it saw (`snapshots/weather/`), and only snapshots are used later.
- **Wikimedia pageviews** of UTC day X: available from X+2 00:00 UTC (lists were seen
  published by midday of X+1). `arena.sources.wikimedia.pageviews_available_at`.
- **ECB fixing** of day X: available from 17:00 Europe/Berlin on X (published ~16:00 CET).
  `arena.sources.ecb.fixing_available_at`.
