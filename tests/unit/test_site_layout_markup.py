"""T233: the layout hooks the stylesheet relies on exist in the built pages."""

from datetime import UTC, datetime
from pathlib import Path

from arena.clock import FixedClock
from arena.ledger import Ledger
from arena.site.build import build_site

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "src" / "arena" / "site" / "static" / "style.css"


def _site(tmp_path):
    clock = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    return build_site(
        Ledger(tmp_path / "l"), tmp_path / "site", clock, ROOT / "site_content"
    ).out_dir


def test_paired_cards_sit_in_a_duo_row(tmp_path) -> None:
    out = _site(tmp_path)
    assert 'class="duo"' in (out / "index.html").read_text()
    recruiters = (out / "recruiters.html").read_text()
    assert recruiters.count('class="duo"') == 1 and 'id="r-what"' in recruiters


def test_stylesheet_has_the_flow_layer_at_zero_specificity() -> None:
    css = CSS.read_text()
    assert ":where(main > .wrap, .game) > :where(* + *)" in css
    assert "--s-4: 1rem" in css and ".duo {" in css


def test_interval_coverage_counts_each_statistic_and_day_once() -> None:
    """T276b: coverage of the experimental band, deduplicated across thresholds."""
    from datetime import date
    from types import SimpleNamespace as NS

    from arena.site.shaping import interval_coverage

    def fc(qid, lo, hi):
        return NS(
            forecaster_id="ml",
            question_id=qid,
            meta={"interval80": {"stat": "mean", "lo": lo, "hi": hi}},
        )

    rec = NS(
        forecasts=[
            fc("a", 40, 60),
            fc("b", 40, 60),
            fc("c", 40, 60),
            NS(forecaster_id="base_rate", question_id="a", meta={}),
        ],
        questions={
            k: NS(target_date=d)
            for k, d in {
                "a": date(2026, 11, 1),
                "b": date(2026, 11, 1),
                "c": date(2026, 11, 2),
            }.items()
        },
        resolutions={
            "a": NS(observed_value=50.0),
            "b": NS(observed_value=50.0),
            "c": NS(observed_value=90.0),
        },
    )
    assert interval_coverage(rec) == {"n": 2, "hits": 1, "share": 0.5}
    assert interval_coverage(NS(forecasts=[], questions={}, resolutions={})) is None
