# Agent tool fixtures

- `wiki_summary_de.json`, `wiki_summary_en.json`: real responses of
  `https://{de,en}.wikipedia.org/api/rest_v1/page/summary/<title>` recorded 2026-11-12,
  unchanged. Wikipedia text is CC BY-SA; only used in tests.
- The RSS sample in `tests/unit/test_agent_tools.py` is synthetic (labelled there): GDELT
  rate-limited this sandbox's shared IP (HTTP 429) when recording was attempted.
