"""Role cards, the German cards, the case-study page and its PDF (T391)."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace as NS

from arena.site.recruiters import ROLE_PATHS, case_results, role_cards

ROOT = Path(__file__).parents[2]
HERO = {
    "ml": "0.1930",
    "persistence": "0.2205",
    "days": "365",
    "diff": "-0.0275",
    "interval": "[-0.0378, -0.0162]",
}
JSON = {"before": "17%", "after": "100%"}


def test_three_cards_with_what_a_number_and_a_code_link() -> None:
    cards = role_cards(ROLE_PATHS, HERO, JSON, {"questions": 10, "forecasts": 50})
    assert [c["role"] for c in cards] == ["AI engineering", "ML and MLOps", "Data science"]
    assert (
        "17%" in cards[0]["number"]
        and "0.1930" in cards[1]["number"]
        and "50 forecasts" in cards[2]["number"]
    )
    for c in cards:
        assert c["what"] and c["code"][1].startswith("src/arena/")
        assert c["code"][1] not in [x[1] for x in c["more"]]


def test_no_data_means_no_number_never_a_guess() -> None:
    cards = role_cards(ROLE_PATHS, None, None, {})
    assert [c["number"] for c in cards] == [None, None, None]


def _lab(exp: str, paired: list, metrics: dict | None = None) -> NS:
    return NS(experiment=exp, paired=paired, metrics=metrics or {})


def test_case_results_copy_the_two_negative_results() -> None:
    p = {"diff": 0.006, "lo": -0.0036, "hi": 0.0152, "n": 87, "split": "eval"}
    m = {
        "agent_committee / eval": {"cost_usd_per_1k": 2.0},
        "agent_skills / eval": {"cost_usd_per_1k": 1.0},
    }
    s = {"diff": 0.0035, "lo": -0.0005, "hi": 0.0077, "n": 1000, "split": "bigmove", "b": "ml"}
    out = case_results([_lab("agent-committee-r2", [p], m), _lab("sentiment", [s])])
    assert out["committee"]["cost_ratio"] == 2.0 and out["sentiment"]["n"] == 1000
    assert case_results([]) == {"committee": None, "sentiment": None}


def test_the_site_has_the_case_study_german_cards_and_the_skills_table_on_the_stack_page() -> None:
    site = ROOT / "_site_e2e"
    if not (site / "case-study.html").is_file():
        import pytest

        pytest.skip("run `make site-e2e` first")
    assert "Can an AI agent beat" in (site / "case-study.html").read_text("utf-8")
    assert "KI- und LLM-Entwicklung" in (site / "de.html").read_text("utf-8")
    assert 'id="skills"' in (site / "stack.html").read_text("utf-8")
    rec = (site / "recruiters.html").read_text("utf-8")
    assert rec.count('class="card role-card"') == 3 and "case-study.html" in rec


def test_the_committed_case_study_pdf_is_one_page() -> None:
    pdf = (ROOT / "docs" / "case-study.pdf").read_bytes()
    assert pdf.startswith(b"%PDF") and len(pdf) > 20_000
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == 1
