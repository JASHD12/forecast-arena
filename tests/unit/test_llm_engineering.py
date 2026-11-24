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


def test_site_without_result_files_has_no_dead_link_to_the_page(tmp_path) -> None:
    """The image has no evals/ directory: the page is omitted and nothing may link to it."""
    from datetime import UTC, datetime

    from arena.clock import FixedClock
    from arena.ledger import Ledger
    from arena.site.build import build_site
    from arena.site.linkcheck import check_site

    empty = tmp_path / "evals"
    empty.mkdir()
    clock = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    res = build_site(Ledger(tmp_path / "l"), tmp_path / "site", clock, evals_dir=empty)
    assert "llm-engineering.html" not in res.pages
    assert check_site(res.out_dir) == []
    for page in ("stack.html", "recruiters.html"):
        assert "llm-engineering.html" not in (res.out_dir / page).read_text(encoding="utf-8")
