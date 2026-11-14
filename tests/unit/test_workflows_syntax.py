"""Workflow files must parse in GitHub's expression grammar (2026-11-14: a comment inside
`${{ ... }}` made every dispatch fail with HTTP 422 while CI stayed green)."""

import re
from pathlib import Path

import yaml

WORKFLOWS = sorted((Path(__file__).resolve().parents[2] / ".github" / "workflows").glob("*.yml"))


def test_every_workflow_is_valid_yaml_with_closed_expressions() -> None:
    assert WORKFLOWS
    for wf in WORKFLOWS:
        text = wf.read_text(encoding="utf-8")
        yaml.safe_load(text)
        for n, line in enumerate(text.splitlines(), 1):
            body = line.split("#", 1)[0] if "${{" not in line else line
            assert body.count("${{") == body.count("}}"), f"{wf.name}:{n}: {line.strip()}"
            for expr in re.findall(r"\$\{\{(.*?)\}\}", line):
                assert "#" not in expr, f"{wf.name}:{n}: comment inside an expression"


def test_scheduled_workflows_default_to_the_live_domains() -> None:
    for name in ("morning", "evening", "resolve"):
        text = (WORKFLOWS[0].parent / f"{name}.yml").read_text(encoding="utf-8")
        assert "vars.ARENA_DOMAINS || 'power,weather,attention,markets'" in text, name
