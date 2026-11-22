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
    assert "Screenshot of the site built from the public ledger on 20" in text  # T213
    assert "**backtests**" in text
    # T184: the first screen carries the pitch, links, one image and generated highlights
    top = text[: text.index("<details>")]
    for must in (
        "Can an LLM agent beat a classical ML model",
        "60-second tour",
        "docs/img/home.png",
        "<!-- highlights:start -->",
        "<!-- headline:start -->",
        "too early to tell",
    ):
        assert must in top, must
    # T212: result, caveat and live status come before the stack, which sits in a details block
    assert text.index("Result so far") < text.index("**Stack:**")
    assert "<summary><strong>Tech stack</strong></summary>" in text
    first15 = "\n".join(text.splitlines()[:25])
    assert "Result so far" in first15 and "Caveat:" in first15
    assert "Status (20" not in text  # no hand-written, dated status paragraph


def test_screenshot_caption_update() -> None:
    """T213: the caption under the screenshot is rewritten with the date; no caption raises."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import pytest
    from screenshots import update_readme

    text = "a\n*Screenshot of x. y*\nb\n"
    out = update_readme(text, "2026-11-19")
    assert "built from the public ledger on 2026-11-19" in out and out.startswith("a\n")
    with pytest.raises(SystemExit):
        update_readme("no caption here", "2026-11-19")


def test_readme_has_role_guide_and_generated_lab_table() -> None:
    """T283: a hiring manager sees a by-role guide and the lab table, both before the stack."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Where to look, by role" in text and "## Experiments lab" in text
    assert text.index("## Where to look, by role") < text.index("**Stack:**")
    block = text[text.index("<!-- lab:start -->") : text.index("<!-- lab:end -->")]
    assert "docs/lab/retrieval-hybrid.md" in block and "docs/lab/qlora-r1.md" in block
    assert "rehearsal phase since the first batch (2026-11-13)" in text


def test_readme_first_screen_has_an_at_a_glance_table_and_current_facts() -> None:
    """The hiring manager's first screen: status table, honest result, fresh screenshot."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    top = text[: text.index("## What this shows")]
    for must in ("**Live since**", "**Status**", "**Who forecasts**", "**Honest so far**"):
        assert must in top, must
    assert top.index("**Live since**") < top.index("<!-- headline:start -->")
    assert "switch on next" not in text and "(live now)" not in text  # stale statements removed
    assert "`llm_local_ft` (experimental)" in text and "agent_graph" in text
    # the highlights carry the generated fine-tune and conformal figures
    hl = text[text.index("<!-- highlights:start -->") : text.index("<!-- highlights:end -->")]
    assert "LLM fine-tuning, measured honestly" in hl and "conformal price bands" in hl
