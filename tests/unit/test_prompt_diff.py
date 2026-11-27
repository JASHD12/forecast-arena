"""The prompt diff report is current, and no prompt version is missing (T383)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
_spec = importlib.util.spec_from_file_location("prompt_diff", ROOT / "scripts" / "prompt_diff.py")
assert _spec and _spec.loader
pd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pd)


def test_report_is_current() -> None:
    res = subprocess.run(
        [sys.executable, "scripts/prompt_diff.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def test_versions_are_consecutive_from_one() -> None:
    for name, versions in pd.families().items():
        assert sorted(versions) == list(range(1, len(versions) + 1)), name


def test_a_real_change_shows_its_lines_and_an_identical_bump_is_marked() -> None:
    text = pd.render({"p": {1: "a\nb\n", 2: "a\nc\n", 3: "a\nc\n"}})
    assert "-b" in text and "+c" in text and "v2 to v3: identical text" in text
