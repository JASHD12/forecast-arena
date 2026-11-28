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
    assert text.index("Forecast Arena") < text.index("Experience")
    assert "too early to tell" in text and "not advice" in text
    assert "backtest, not the live record" in text
    assert "[FILL IN" not in text and "TODO" not in text


def test_contact_lines_appear_only_when_the_owner_supplied_them() -> None:
    text = pr.render()
    from arena.site.recruiters import load_facts

    facts = load_facts(ROOT / "site_content")
    has_contact = any(k in facts for k in ("cv_url", "linkedin", "email"))
    assert ("[CV (PDF)]" in text or "[LinkedIn]" in text or "mailto:" in text) == has_contact


def test_every_link_to_the_site_names_an_existing_page() -> None:
    from arena.site.content import NAV_MORE

    pages = {"ask.html", "recruiters.html", "status.html"}
    text = pr.render()
    for p in pages:
        assert pr.SITE + p in text
    assert "ask.html" in {n for n, _ in NAV_MORE} and (ROOT / "examples/forecast-audit").exists()


def test_draft_is_short_and_has_no_phone_visa_or_completed_degree() -> None:
    import re

    text = pr.render()
    assert len(text.encode("utf-8")) <= 7000
    assert not re.search(r"\+49|\d{4} \d{7}|AufenthG|[Vv]isa", text)
    assert "expected" in text and "M.Sc. in Data Science from" not in text
    assert "Hamburg" not in text


def test_email_only_when_supplied_and_every_number_is_generated() -> None:
    import re

    from arena.site.recruiters import load_facts

    text = pr.render()
    email = load_facts(ROOT / "site_content").get("email")
    assert (f"mailto:{email}" in text) == bool(email)
    source = pr.rs.headline() + pr.rs.highlights()
    for num in re.findall(r"\b0\.\d{4}\b", text):
        assert num in source


def test_cv_sections_split_by_heading() -> None:
    secs = pr.cv_sections("lead\n\n## A\nx\n## B: c\ny")
    assert secs == {"": "lead", "A": "x", "B: c": "y"}
