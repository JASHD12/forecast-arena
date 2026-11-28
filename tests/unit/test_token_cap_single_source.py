"""The daily token cap (code default, three workflows, SPEC 9.4) is one number (T383)."""

from __future__ import annotations

import re
from pathlib import Path

from arena.config import Settings

ROOT = Path(__file__).parents[2]
FLOW = re.compile(r"ARENA_LLM_MAX_TOKENS_PER_DAY:.*?\|\|\s*'(\d+)'")


def test_workflow_defaults_equal_the_code_default() -> None:
    cap = Settings.from_env({}).llm_max_tokens_per_day
    seen = {}
    for name in ("morning.yml", "evening.yml", "resolve.yml"):
        m = FLOW.search((ROOT / ".github/workflows" / name).read_text("utf-8"))
        assert m, f"{name} does not set the cap"
        seen[name] = int(m.group(1))
    assert set(seen.values()) == {cap}, f"cap differs: code {cap}, workflows {seen}"


def test_spec_states_the_same_cap() -> None:
    cap = Settings.from_env({}).llm_max_tokens_per_day
    spec = (ROOT / "docs/SPEC.md").read_text("utf-8")
    row = next(ln for ln in spec.splitlines() if ln.startswith("| `ARENA_LLM_MAX_TOKENS_PER_DAY`"))
    assert str(cap) in row.replace(",", "")
