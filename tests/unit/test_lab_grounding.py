"""T252a: numeric grounding of rationales."""

import json
from pathlib import Path

import pytest

from arena.lab import grounding as gr

ROOT = Path(__file__).resolve().parents[2]


def test_numbers_are_parsed_with_decimals_commas_and_without_dates() -> None:
    got = gr.numbers_in("Price 246.5 EUR on 2026-11-20, volume 1,500 and 61% up, -12.25")
    assert got == [(246.5, 1), (1500.0, 0), (61.0, 0), (-12.25, 2)]
    assert gr.numbers_in("no numbers") == []


def test_trivial_numbers_are_ignored() -> None:
    assert gr.is_trivial(3, 0) and gr.is_trivial(2026, 0)
    assert not gr.is_trivial(3.5, 1) and not gr.is_trivial(246, 0)
    assert gr.check("3 of the last 7 days in 2026", [], {}) == {"grounded": 0, "not_in_prompt": 0}


def test_grounded_within_rounding_or_one_percent() -> None:
    ctx = {
        "prices": [{"day": "2026-11-18", "mean": 197.72}, {"mean": 143.0}],
        "note": "peak 314 EUR",
    }
    c = gr.check("mean 197.7 and 198, peak 314, low 143, invented 523", ["threshold 246"], ctx)
    assert c == {"grounded": 4, "not_in_prompt": 1}
    assert gr.check("threshold of 246", ["threshold 246"], {})["grounded"] == 1


def test_booleans_and_strings_in_the_context() -> None:
    assert gr.context_numbers({"a": True, "b": "price 12.5", "c": [1, {"d": 2.5}]}) == [
        12.5,
        1.0,
        2.5,
    ]


def test_summary_rates() -> None:
    s = gr.summarize([{"grounded": 3, "not_in_prompt": 1}, {"grounded": 2, "not_in_prompt": 0}])
    assert s == {
        "n": 2,
        "numbers": 6,
        "not_in_prompt_pct": 16.7,
        "rationales_with_not_in_prompt_pct": 50.0,
    }
    assert gr.summarize([])["n"] == 0


def test_committed_result_matches_the_schema() -> None:
    path = ROOT / "evals" / "results" / "lab-grounding.json"
    if not path.is_file():
        pytest.skip("grounding result not committed in this checkout")
    from arena.lab.results import LabResult

    r = LabResult.model_validate(json.loads(path.read_text()))
    assert r.experiment == "grounding" and "llm_plain" in r.metrics and r.cost_usd == 0
