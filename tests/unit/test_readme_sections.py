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
    # T390: the first screen is the one-line pitch, the standings chart, generated result bullets
    # and the recruiter link; everything else is behind the first <details> block
    top = text[: text.index("<details>")]
    for must in (
        "A live benchmark where an AI agent and a classical ML model forecast tomorrow",
        "docs/img/standings.svg",
        "<!-- top:start -->",
        "<!-- topcaption:start -->",
        "60 s",
        "recruiters.html",
    ):
        assert must in top, must
    full = text[text.index("<details>") :]
    for must in (
        "Can an LLM agent beat a classical ML model",
        "60-second tour",
        "docs/img/home.png",
        "<!-- highlights:start -->",
        "<!-- headline:start -->",
        "too early to tell",
    ):
        assert must in full, must
    # T212: result, caveat and live status come before the stack, which sits in a details block
    assert text.index("Result so far") < text.index("**Stack:**")
    assert "<summary><strong>Tech stack</strong></summary>" in text
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
    assert "days before 2026-11-23 are rehearsal" in text
    assert "official record has run since" in text


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


def test_first_30_lines_answer_role_result_what_i_built_and_contact() -> None:
    """T390: a reader gets the pitch, the chart, three generated results, what was built and the
    recruiter link in the first 30 lines."""
    lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()[:30]
    head = "\n".join(lines)
    assert lines[0] == "# Forecast Arena"
    assert "docs/img/standings.svg" in head
    bullets = [ln for ln in lines if ln.startswith("- **") and "Brier" in ln]
    assert len(bullets) >= 3, "three generated result bullets with their numbers"
    assert "**What I built:**" in head and "**For recruiters (60 s):**" in head
    assert "recruiters.html" in head and "<!-- contact:start -->" in head


def test_top_bullets_are_generated_from_committed_data() -> None:
    """I5: the bullets come from docs/data/standings.json and the lab results, not from typing."""
    import json
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import readme_sections as rs

    snap = json.loads((ROOT / "docs" / "data" / "standings.json").read_text(encoding="utf-8"))
    weather = {r["id"]: r for r in snap["topics_all_days"]["weather"]["rows"]}
    text = rs.top()
    assert f"{weather['ml']['brier']:.3f}" in text and f"{weather['agent']['brier']:.3f}" in text
    assert snap["official_start"] in rs.top_caption()
    assert "too early to tell" in rs.top_caption() or snap["official"]["label"] is None
