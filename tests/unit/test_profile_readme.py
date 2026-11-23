"""The GitHub profile README draft (T326): generated, current, and free of invented facts."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import profile_readme as pr  # noqa: E402


def test_committed_draft_is_current() -> None:
    assert pr.OUT.read_text(encoding="utf-8") == pr.render()


def test_draft_leads_with_the_project_and_keeps_the_caveats() -> None:
    text = pr.render()
    assert text.index("Featured project: Forecast Arena") < text.index("What it shows")
    assert "too early to tell" in text and "not advice" in text
    assert "backtest, not the live record" in text
    assert "[FILL IN" not in text and "TODO" not in text


def test_contact_lines_appear_only_when_the_owner_supplied_them() -> None:
    text = pr.render()
    facts = (ROOT / "site_content" / "recruiter_facts.json").exists()
    assert ("[CV (PDF)]" in text or "[LinkedIn]" in text or "[Email]" in text) == facts


def test_every_link_to_the_site_names_an_existing_page() -> None:
    from arena.site.content import NAV_MORE

    pages = {"ask.html", "recruiters.html", "audit.html", "status.html"}
    text = pr.render()
    for p in pages:
        assert pr.SITE + p in text
    assert "ask.html" in {n for n, _ in NAV_MORE} and (ROOT / "examples/forecast-audit").exists()
