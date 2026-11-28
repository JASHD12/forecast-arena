"""Registration order of the forecasters (T383): peers before the forecasters that read them."""

from __future__ import annotations

from pathlib import Path

from factories import B

from arena.config import Settings
from arena.ledger import Ledger
from arena.llm.client import FakeLLM
from arena.ops.wiring import build_forecasters

#: Every flag that works offline (no model download); the others are covered by their own tests.
ENV = {
    "ARENA_LLM_PLAIN": "1",
    "ARENA_AGENT_QUANT": "1",
    "ARENA_AGENT_ANALYST": "1",
    "ARENA_AGENT_SKILLS": "1",
    "ARENA_AGENT_GRAPH": "1",
    "ARENA_AGENT_GRAPH_SKILLS": "1",
    "ARENA_AGENT_COMMITTEE": "1",
    "ARENA_LLM_CONTEXT_CAL": "1",
    "ARENA_BANDIT": "1",
    "ARENA_AGENT_RAG": "0",
}
EXPECTED = [
    "base_rate",
    "persistence",
    "ml",
    "llm_plain",
    "llm_context",
    "agent",
    "agent_quant",
    "agent_analyst",
    "agent_skills",
    "agent_graph",
    "agent_graph_skills",
    "agent_committee",
    "llm_context_cal",
    "bandit_hedge",
]


def _ids(tmp_path: Path, env: dict[str, str]) -> list:
    out, _ = build_forecasters(Ledger(tmp_path), [], Settings.from_env(env), B, llm=FakeLLM(["x"]))
    return out


def test_registration_order_is_pinned(tmp_path: Path) -> None:
    assert [f.forecaster_id for f in _ids(tmp_path, ENV)] == EXPECTED


def test_forecasters_that_read_peers_come_after_everything_they_read(tmp_path: Path) -> None:
    out = _ids(tmp_path, ENV)
    ids = [f.forecaster_id for f in out]
    readers = [i for i, f in enumerate(out) if getattr(f, "needs_peers", False)]
    assert readers and min(readers) > ids.index("llm_context") and min(readers) > ids.index("agent")
    assert readers == list(range(min(readers), len(out)))  # the readers are the tail


def test_the_roster_in_the_catalog_matches_what_is_registered(tmp_path: Path) -> None:
    from arena.ops.health import expected_forecasters

    s = Settings.from_env(ENV)
    assert {f.forecaster_id for f in _ids(tmp_path, ENV)} == set(expected_forecasters(s))


def test_default_settings_register_the_core_forecasters(tmp_path: Path) -> None:
    from arena.forecasters.catalog import CORE_FORECASTERS

    ids = [f.forecaster_id for f in _ids(tmp_path, {})]
    assert set(ids) == set(CORE_FORECASTERS) and ids[:3] == ["base_rate", "persistence", "ml"]


def test_version_strings_are_pinned(tmp_path: Path) -> None:
    """A prompt, tool-set or map change must show up here as a deliberate diff (I8)."""
    import json
    import re

    snap = json.loads(Path("tests/fixtures/forecaster_versions_snapshot.json").read_text("utf-8"))

    def norm(v: str) -> str:  # library versions are pinned by requirements, not by this test
        return re.sub(r"\b(langgraph|sdk)-\d+(\.\d+)*", r"\1-X", v)

    got = {f.forecaster_id: norm(f.version()) for f in _ids(tmp_path, ENV)}
    assert got == {k: norm(v) for k, v in snap.items()}
