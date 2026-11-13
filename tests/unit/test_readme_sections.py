"""T142: the generated README blocks must match the model cards and the skills list."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_readme_generated_sections_are_current() -> None:
    r = subprocess.run(
        [sys.executable, "scripts/readme_sections.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_readme_screenshots_exist_and_are_labelled() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in ("home", "play", "leaderboard"):
        assert f"docs/img/{name}.png" in text
        assert (ROOT / "docs" / "img" / f"{name}.png").stat().st_size > 1000
    assert "offline demo build (fixture data)" in text
    assert "**backtests**" in text
    # T184: the first screen carries the pitch, links, one image and generated highlights
    top = text[: text.index("<details>")]
    for must in (
        "Can an LLM agent beat a classical ML model",
        "60-second tour",
        "docs/img/home.png",
        "<!-- highlights:start -->",
        "**Stack:**",
    ):
        assert must in top, must
    assert "Status (20" not in text  # no hand-written, dated status paragraph
