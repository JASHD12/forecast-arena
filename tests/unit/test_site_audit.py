"""Forecast audit case page (T322): generated from the report, honest, omitted without data."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from arena.clock import FixedClock
from arena.ledger import Ledger
from arena.site import forecast_audit as fa
from arena.site.build import build_site
from arena.site.linkcheck import check_site

CLOCK = FixedClock(datetime(2026, 11, 23, tzinfo=UTC))
ROOT = Path(__file__).resolve().parents[2]
EX = ROOT / "examples" / "forecast-audit" / "german-electricity"


def _site(tmp: Path, **kw):
    return build_site(Ledger(tmp / "l"), tmp / "site", CLOCK, tmp / "none", **kw)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_headlines_are_generated_from_the_report() -> None:
    case = fa.load_case()
    assert case is not None
    report = json.loads((EX / "expected" / "report.json").read_text())
    assert case["n"] == report["time_scope"]["cases"] == 46 and case["yes"] == 29
    assert case["same_decisions"] and case["differing_decisions"] == 0
    assert "46 historischen Strompreisfällen" in case["headline_de"]
    assert (
        "Alarmschwelle von 20 %" in case["headline_de"]
        and "17 Alarme waren Fehlalarme" in case["headline_de"]
    )
    assert "0.2337" in case["headline_en"] and "0.2499" in case["headline_en"]
    assert "exactly the same days" in case["headline_en"] and "20%" in case["headline_en"]


def test_examples_follow_a_stated_rule_at_the_equal_cost_cutoff() -> None:
    case = fa.load_case()
    ex = case["examples"]
    assert ex["cutoff"] == 0.5
    for kind, outcome in (("helped", 0), ("hurt", 1)):
        row = ex[kind]
        if (
            row
        ):  # the first qualifying day by date, model below the cutoff, base rate at or above it
            assert row["outcome"] == outcome and row["p_model"] < 0.5 <= row["p_base"]


def test_page_states_scope_and_links_to_the_contract(tmp_path: Path) -> None:
    res = _site(tmp_path)
    page = (res.out_dir / "audit.html").read_text()
    text = _text(page)
    assert (
        "Replay, not a live result" in text
        and "replayed" in text
        and "Research project, not advice" in text
    )
    assert (
        "assumed" in text and "classical gradient-boosted model is not in this comparison" in text
    )
    assert "examples/forecast-audit/SCHEMA.md" in page and "no price series" in text
    assert (
        page.count("audit-chart audit-") == 2 and "aria-labelledby" in page
    )  # two layouts of the one chart
    assert 'href="audit.html"' in (res.out_dir / "index.html").read_text()  # in the More menu
    assert check_site(res.out_dir) == []


def test_recruiter_entries_and_the_german_line(tmp_path: Path) -> None:
    res = _site(tmp_path)
    student = _text((res.out_dir / "recruiters.html").read_text())
    engineer_html = (res.out_dir / "recruiters-ml.html").read_text()
    engineer = _text(engineer_html)
    assert "Werkstudent AI / Machine Learning" in student and "Backend engineer" not in student
    assert "Jashdeep Singh" in engineer and "Backend engineer" not in engineer
    assert "Explore the electricity case" in student and "Explore the electricity case" in engineer
    assert 'href="recruiters-ml.html"' not in (res.out_dir / "recruiters.html").read_text()
    _, _, after_hero_start = engineer_html.partition('<section class="hero recruiter-hero">')
    hero = after_hero_start.partition("</section>")[0]
    assert hero
    assert "This is the full-time ML engineering version" not in engineer
    assert 'href="recruiters.html"' not in hero
    assert "AI-assisted development" not in student and "AI-assisted development" not in engineer
    assert (
        "Download CV" not in engineer and "Contact on LinkedIn" not in engineer
    )  # no owner facts given
    de = _text((res.out_dir / "de.html").read_text())
    assert (
        "In 46 historischen Strompreisfällen lösten beide Modelle bei einer Alarmschwelle von 20 %"
        in de
    )


def test_owner_facts_show_a_contact_action_when_supplied(tmp_path: Path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    (content / "recruiter_facts.json").write_text(
        json.dumps({"cv_url": "https://example.org/cv.pdf"})
    )
    res = build_site(Ledger(tmp_path / "l"), tmp_path / "site", CLOCK, content)
    assert "Download CV (PDF)" in (res.out_dir / "recruiters-ml.html").read_text()


def test_without_the_case_files_the_pages_and_the_menu_entry_are_omitted(tmp_path: Path) -> None:
    res = _site(tmp_path, audit_dir=tmp_path / "missing")
    assert "audit.html" not in res.pages and "recruiters-ml.html" not in res.pages
    assert "audit.html" not in (res.out_dir / "index.html").read_text()
    assert check_site(res.out_dir) == []


def test_lineage_reads_the_ledger_record() -> None:
    q = SimpleNamespace(
        text="Will it?",
        batch_date=datetime(2026, 11, 16).date(),
        target_date=datetime(2026, 11, 17).date(),
        lock_time=datetime(2026, 11, 16, 9, 30, tzinfo=UTC),
    )
    rec = SimpleNamespace(
        questions={"q": q},
        forecasts=[SimpleNamespace(question_id="q", forecaster_id="ml", probability=0.19)],
        skips=[
            SimpleNamespace(question_id="q", forecaster_id="agent_graph", reason_code="not_sampled")
        ],
        resolutions={"q": SimpleNamespace(outcome=0)},
    )
    got = fa.lineage(rec, "q")
    assert got["ml"] == 0.19 and got["persistence"] is None and got["outcome"] == 0
    assert got["skips"] == {"agent_graph": "not_sampled"} and fa.lineage(rec, "zz") is None


def test_home_and_guide_say_the_official_record_started_when_the_start_file_exists(
    tmp_path: Path,
) -> None:
    import json

    from arena.ledger import layout

    plain = _site(tmp_path / "a")
    assert "The official record started on" not in _text((plain.out_dir / "index.html").read_text())
    led = Ledger(tmp_path / "b" / "l")
    led.write_raw(layout.OFFICIAL_START_PATH, json.dumps({"official_start": "2026-11-23"}).encode())
    res = build_site(led, tmp_path / "b" / "site", CLOCK, tmp_path / "none")
    home = _text((res.out_dir / "index.html").read_text())
    assert "The official record started on 2026-11-23" in home
    assert "none of its questions has resolved yet" in home and "Standings rehearsal" in home
    board = _text((res.out_dir / "leaderboard.html").read_text())
    assert "none of its questions has resolved yet" in board
    assert "It started on 2026-11-23" in _text((res.out_dir / "guide.html").read_text())
