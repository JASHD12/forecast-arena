"""The LLM engineering page (T325): numbers equal the result files; omitted without them."""

from __future__ import annotations

import json
from pathlib import Path

from arena.site import llm_engineering as le

RES = Path(__file__).resolve().parents[2] / "evals" / "results"


def test_numbers_equal_result_files() -> None:
    page = le.load_page(RES)
    assert page is not None
    ds = json.loads((RES / "lab-distill-r1.json").read_text())
    st = ds["metrics"]["distill_1_5b / test_all"]["brier"]
    te = ds["metrics"]["claude_teacher / test_all"]["brier"]
    row = next(r for r in page["rows"] if r["key"] == "distill")
    assert f"{st:.4f}" in row["result"] and f"{te:.4f}" in row["result"]
    assert page["n"] == ds["metrics"]["base_rate / test_all"]["n"]
    briers = [v for _, v, _ in page["arms"]]
    assert briers == sorted(briers)


def test_routing_sentence_is_honest_about_zero_savings() -> None:
    page = le.load_page(RES)
    assert page is not None
    row = next(r for r in page["rows"] if r["key"] == "routing")
    assert "avoided 0.0%" in row["result"] and "76.1%" in row["result"]


def test_omitted_without_results(tmp_path: Path) -> None:
    assert le.load_page(tmp_path, tmp_path / "none.md") is None


def test_budget_costs_parse() -> None:
    assert le.budget_costs()["distill"] > 0
    assert le.budget_costs(Path("/nonexistent"))["judge"] == 0.0


def test_chart_svg_has_accessible_title_and_every_arm() -> None:
    svg = str(le.chart_svg([("A", 0.2, "s-1"), ("B", 0.25, "s-5")]))
    assert "<title" in svg and "A" in svg and "0.2000" in svg and "0.2500" in svg
