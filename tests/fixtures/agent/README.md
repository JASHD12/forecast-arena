# Agent tool fixtures

- `wiki_summary_de.json`, `wiki_summary_en.json`: real responses of
  `https://{de,en}.wikipedia.org/api/rest_v1/page/summary/<title>` recorded 2026-11-12,
  unchanged. Wikipedia text is CC BY-SA; only used in tests.
- `gdelt_artlist.rss`: real GDELT DOC API response (ArtList, RSS) recorded 2026-11-12 for
  `query=strompreis`, 5-12 Nov 2026: a valid feed with no items. Earlier attempts from this
  sandbox's shared IP got HTTP 429, so the item-level parser test uses a synthetic sample
  (labelled in `tests/unit/test_agent_tools.py`).
