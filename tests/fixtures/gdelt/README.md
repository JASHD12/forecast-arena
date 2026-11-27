# GDELT fixtures

Real responses of `https://api.gdeltproject.org/api/v2/doc/doc` for the query `bitcoin sourcelang:english`,
`mode=TimelineTone` and `mode=TimelineVolRaw`, `format=json`, 2026-11-01 to 2026-11-10, recorded on
2026-11-27 at about 17:11 UTC by `scripts/record_gdelt_fixture.py` from the owner's computer (the
sandbox and the GitHub runner were rate limited by GDELT). The bodies are unmodified; `provenance.json`
has the URL, status, time and SHA-256 of each (a test checks the hashes).

Days 1 and 2 November are absent from the responses: days without matching articles are not
returned, so the parser never fills them.

Data: GDELT Project (https://www.gdeltproject.org/).
