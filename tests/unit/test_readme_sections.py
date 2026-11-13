"""T142: the generated README blocks must match the model cards and the skills list."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_readme_generated_sections_are_current() -> None:
    r = subprocess.run([sys.executable, "scripts/readme_sections.py", "--check"],
                       cwd=ROOT, capture_output=True, text=True)  # fmt: skip
    assert r.returncode == 0, r.stdout + r.stderr


def test_readme_screenshots_exist_and_are_labelled() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in ("home", "play", "leaderboard"):
        assert f"docs/img/{name}.png" in text
        assert (ROOT / "docs" / "img" / f"{name}.png").stat().st_size > 1000
    assert "fixture data, not the live record" in text
    assert "**backtests**" in text
