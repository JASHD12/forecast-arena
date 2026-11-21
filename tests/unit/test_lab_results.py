"""T242: lab result schema, the Lab page and the budget rule."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from arena.clock import FixedClock
from arena.lab.results import (
    BUDGET_LIMIT_USD,
    LabResult,
    check_budget,
    lab_cards,
    load_lab_results,
    total_cost,
)
from arena.ledger import Ledger
from arena.site.build import build_site

ROOT = Path(__file__).resolve().parents[2]


def _result(**kw) -> dict:
    base = {
        "kind": "evaluation",
        "experiment": "demo",
        "title": "Demo experiment",
        "created_at": "2026-11-21T12:00:00Z",
        "why": "Companies tune small models to cut cost (source S1).",
        "metrics": {
            "base": {"n": 10, "brier": 0.25},
            "tuned": {"n": 10, "brier": 0.2, "ece": 0.05},
        },
        "paired": [{"a": "tuned", "b": "base", "diff": -0.05, "lo": -0.1, "hi": 0.01, "n": 10}],
        "cost_usd": 0.3,
        "notes": ["small sample"],
    }
    return {**base, **kw}


def test_schema_round_trip_and_unknown_fields_are_refused(tmp_path) -> None:
    r = LabResult.model_validate(_result())
    assert LabResult.model_validate(json.loads(r.model_dump_json())) == r
    with pytest.raises(ValueError):
        LabResult.model_validate(_result(surprise=1))
    with pytest.raises(ValueError):
        LabResult.model_validate(_result(kind="live"))


def test_loading_orders_newest_first_and_cards_show_only_present_columns(tmp_path) -> None:
    (tmp_path / "lab-a.json").write_text(json.dumps(_result(experiment="a")))
    (tmp_path / "lab-b.json").write_text(
        json.dumps(_result(experiment="b", created_at="2026-11-22T00:00:00Z"))
    )
    (tmp_path / "eval-x.json").write_text("not json")  # not a lab file: never read
    got = load_lab_results(tmp_path)
    assert [r.experiment for r in got] == ["b", "a"]
    assert lab_cards(got)[0]["cols"] == ["n", "brier", "ece"]
    assert load_lab_results(tmp_path / "missing") == []


def test_budget_rule() -> None:
    a, b = LabResult.model_validate(_result()), LabResult.model_validate(_result(cost_usd=1.5))
    assert total_cost([a, b]) == pytest.approx(1.8)
    assert check_budget([a, b]) == pytest.approx(1.8)
    with pytest.raises(ValueError):
        check_budget([a, b, b])


def test_committed_lab_results_stay_within_the_budget() -> None:
    results = load_lab_results(ROOT / "evals" / "results")
    assert check_budget(results) <= BUDGET_LIMIT_USD


def test_lab_page_has_the_banner_and_never_feeds_the_boards(tmp_path) -> None:
    results = tmp_path / "evals"
    results.mkdir()
    (results / "lab-demo.json").write_text(json.dumps(_result()))
    clock = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    out = build_site(
        Ledger(tmp_path / "l"), tmp_path / "site", clock, ROOT / "site_content", evals_dir=results
    ).out_dir
    lab = (out / "lab.html").read_text()
    assert "<strong>EVALUATION</strong>" in lab and "Demo experiment" in lab
    assert "interval includes zero" in lab and "US$0.30" in lab
    for page in ("index.html", "leaderboard.html", "findings.html", "evals.html"):
        assert "Demo experiment" not in (out / page).read_text(), page
    assert "lab.html" in (out / "index.html").read_text()  # in the navigation


def test_empty_lab_page_says_so(tmp_path) -> None:
    clock = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    out = build_site(
        Ledger(tmp_path / "l"), tmp_path / "site", clock, ROOT / "site_content"
    ).out_dir
    assert "No experiment has finished yet" in (out / "lab.html").read_text()
