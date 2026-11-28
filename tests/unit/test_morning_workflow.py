"""The morning workflow's dry-run switches cannot turn an experimental forecaster on live (T398)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
FLOW = (ROOT / ".github/workflows/morning.yml").read_text("utf-8")
AGENT_LINES = re.findall(r"^      (ARENA_AGENT_(?!GRAPH:|RAG:)[A-Z_]+): (.*)$", FLOW, re.M)


def test_every_experimental_agent_flag_is_switched_by_a_dry_run_only() -> None:
    assert len(AGENT_LINES) == 7
    for var, expr in AGENT_LINES:
        fid = var.removeprefix("ARENA_").lower()
        # both dry-run switches sit inside the dry_run guard; the live value is the variable
        assert f"(inputs.dry_run && (inputs.experimental || inputs.only == '{fid}'))" in expr, var
        expr = expr.split("}}")[0] + "}}"  # drop the trailing comment
        assert expr.endswith(f"&& '1' || vars.{var} || '0' }}}}"), var


def test_the_only_input_lists_exactly_the_experimental_agents() -> None:
    block = FLOW.split("      only:\n", 1)[1].split("        default:", 1)[0]
    options = re.findall(r"^          - (\S*)$", block, re.M)
    assert options[0] == '""'
    assert options[1:] == [v.removeprefix("ARENA_").lower() for v, _ in AGENT_LINES]
