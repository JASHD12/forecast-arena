# Attention fixtures

`recorded.json.gz` is a recording of a real run of `AttentionDomain` against the live
Wikimedia and Wikidata APIs on 2026-11-12 (batches 2026-11-08 and 2026-11-12), made with
`RecordingSource` in `tests/unit/attention_fixtures.py`. Top lists are trimmed to their
first 300 entries (the domain saw the same trimmed lists while recording); Wikidata P31
answers and per-article series are stored as returned.
