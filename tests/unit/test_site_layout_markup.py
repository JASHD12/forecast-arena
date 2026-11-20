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
