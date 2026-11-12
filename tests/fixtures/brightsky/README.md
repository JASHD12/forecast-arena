# Bright Sky fixtures

Real responses of `https://api.brightsky.dev/weather` recorded on 2026-11-12 at about
11:29 UTC with the project User-Agent, stored unchanged. Data: Deutscher Wetterdienst
(DWD), CC BY 4.0, via Bright Sky.

Query: `dwd_station_id=<id>&date=<day>T00:00:00+01:00&last_date=<day+1>T00:00:00+01:00&tz=Europe/Berlin&units=dwd`

| File | Station | Content |
|---|---|---|
| `obs_<id>_2026-11-10.json` | 01420 Frankfurt/Main, 00403 Berlin-Dahlem, 01975 Hamburg-Fuhlsbüttel, 01262 München-Flughafen | observations (historical) for 10 Nov 2026 |
| `fc_<id>_2026-11-13.json` | same | DWD MOSMIX forecast for 13 Nov 2026, as published on the morning of 12 Nov |
| `obs_<id>_2026-08-08.json.gz` | all four | observations 8 Aug 2026 00:00 to 12 Nov 2026 00:00 local, recorded 2026-11-12 ~11:35 UTC. **Reduced**: each record keeps only `timestamp`, `source_id`, `temperature`, `precipitation`, `fallback_source_ids`; `sources` unchanged; gzipped. |
