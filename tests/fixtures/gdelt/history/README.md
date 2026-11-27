# GDELT daily history (raw chunks)

Unmodified GDELT DOC 2.0 responses (`mode=TimelineTone` and `mode=TimelineVolRaw`, `format=json`) for the five
coin queries of `lab/prereg/sentiment.md`, in 90-day chunks from 2025-11-01 to 2026-11-10, recorded on 2026-11-27
by the `gdelt-record` workflow on a GitHub runner (`scripts/record_gdelt_history.py`). `manifest.json` has the
URL, time and SHA-256 of every saved chunk; chunks GDELT refused (HTTP 429) are not here and are fetched by
later runs of the same script. Nothing is filled or interpolated.

Data: GDELT Project (https://www.gdeltproject.org/).
