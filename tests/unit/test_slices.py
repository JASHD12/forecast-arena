"""T220: backtest slices are computed from records, paired, and honestly worded."""

from datetime import date, timedelta

from arena.backtest.harness import BacktestRecord
from arena.backtest.slices import MIN_QUESTIONS, markdown, slice_rows, statement


def _rec(day: date, q: int, fid: str, p: float, y: int, template: str = "mean_gt"):
    return BacktestRecord(
        run_id="r",
        question_id=f"q{day}-{q}",
        domain="power",
        template=template,
        entity="DE_LU",
        batch_date=day,
        forecaster_id=fid,
        forecaster_version="1",
        probability=p,
        outcome=y,
    )


def _records(days: int = 60) -> list[BacktestRecord]:
    out = []
    for i in range(days):
        d = date(2026, 3, 1) + timedelta(days=i)
        y = i % 2
        out.append(_rec(d, 0, "ml", 0.9 if y else 0.1, y))  # sharp and right
        out.append(_rec(d, 0, "persistence", 0.5, y))  # uninformative
        out.append(_rec(d, 1, "ml", 0.5, y, "min_lt"))  # no better than persistence here
        out.append(_rec(d, 1, "persistence", 0.5, y, "min_lt"))
    return out


def test_slices_pair_the_same_questions_and_label_verdicts() -> None:
    rows = slice_rows(_records())
    by = {(r.group, r.name): r for r in rows}
    t = by[("template", "mean_gt")]
    assert t.n == 60 and t.days == 60 and t.brier_a < t.brier_b and t.verdict == "first is better"
    assert by[("template", "min_lt")].verdict == "no supported difference"
    assert {r.group for r in rows} == {"template", "month", "target day"}
    assert sum(r.n for r in rows if r.group == "month") == 120


def test_small_slices_are_never_described() -> None:
    rows = slice_rows(_records(10))
    assert all(r.verdict == "too few questions" for r in rows if r.n < MIN_QUESTIONS)
    assert "not clearly worse" not in statement([r for r in rows if r.n < MIN_QUESTIONS])


def test_statement_names_slices_where_persistence_is_not_worse() -> None:
    s = statement(slice_rows(_records()))
    assert "template min_lt" in s and "template mean_gt" not in s


def test_unresolved_and_unpaired_records_are_ignored() -> None:
    recs = _records(30)
    recs.append(_rec(date(2026, 5, 1), 9, "ml", 0.7, 1))  # no persistence partner
    assert sum(r.n for r in slice_rows(recs) if r.group == "template") == 60


def test_markdown_is_labelled_backtest_and_has_all_tables() -> None:
    md = markdown(_records(), "run-x")
    assert md.startswith("# Backtest slices") and "BACKTEST, not the live record" in md
    for g in ("template", "month", "target day"):
        assert f"**By {g}**" in md


def test_committed_slice_card_matches_the_stored_run() -> None:
    """The card in docs/models is exactly what the stored backtest run produces.

    Backtest runs are not committed (`backtests/` is git-ignored), so the byte-for-byte
    reproduction only runs where the run exists; the committed-file checks below always run."""
    import re
    from pathlib import Path

    import pytest

    from arena.backtest.harness import BacktestStore

    root = Path(__file__).resolve().parents[2]
    card = (root / "docs" / "models" / "power-slices.md").read_text(encoding="utf-8")
    run_id = re.search(r"\(run `([^`]+)`\)", card).group(1)  # type: ignore[union-attr]
    # always: same run as the power card, and all three tables are present
    assert run_id in (root / "docs" / "models" / "power.md").read_text(encoding="utf-8")
    for g in ("template", "month", "target day"):
        assert f"**By {g}**" in card
    run_file = root / "backtests" / run_id / "forecasts.jsonl"
    if not run_file.is_file():
        pytest.skip("stored backtest run not available (backtests/ is not committed)")
    records = BacktestStore(root / "backtests").read(run_id)
    assert markdown(records, run_id) == card
