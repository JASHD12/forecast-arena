"""Chunking of the GDELT history recorder (T371); the network part is not tested here."""

from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from itertools import pairwise
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "record_gdelt_history", Path(__file__).parents[2] / "scripts" / "record_gdelt_history.py"
)
assert _spec and _spec.loader
rec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rec)


def test_chunks_cover_the_range_without_gaps_or_overlap() -> None:
    parts = rec.chunks(date(2025, 11, 1), date(2026, 11, 10))
    assert parts[0][0] == date(2025, 11, 1) and parts[-1][1] == date(2026, 11, 10)
    for (_, e), (s, _) in pairwise(parts):
        assert s == e + timedelta(days=1)
    assert all((e - s).days < rec.CHUNK_DAYS for s, e in parts)


def test_queries_are_the_preregistered_five() -> None:
    assert list(rec.QUERIES) == ["bitcoin", "ethereum", "solana", "ripple", "binancecoin"]
    assert all("sourcelang:english" in q for q in rec.QUERIES.values())
