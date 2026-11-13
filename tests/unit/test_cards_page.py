"""Backtests page (T135)."""

from datetime import UTC, datetime
from pathlib import Path

from arena.clock import FixedClock
from arena.ledger import Ledger
from arena.site.build import build_site
from arena.site.cards_page import load_cards, render_card

MODELS = Path(__file__).resolve().parents[2] / "docs" / "models"


def test_renderer_escapes_and_renders_tables_lists_bold_code() -> None:
    md = (
        "**What.** uses `HistGradientBoosting` <script>alert(1)</script>\n\n"
        "| Forecaster | n | Brier |\n|---|---|---|\n| ml | 10 | 0.19 |\n\n"
        "- one\n- two\n\n## Backtest\n\n[link](https://example.org)"
    )
    h = str(render_card(md, "x"))
    assert "<script>" not in h and "&lt;script&gt;" in h
    assert "<strong>What.</strong>" in h and "<code>HistGradientBoosting</code>" in h
    assert '<th scope="row">ml</th>' in h and '<td class="num">0.19</td>' in h
    assert "<ul><li>one</li><li>two</li></ul>" in h and "<h3>Backtest</h3>" in h
    assert '<a href="https://example.org">link</a>' in h


def test_committed_cards_are_all_on_the_page(tmp_path) -> None:
    cards = load_cards(MODELS)
    assert [c["stem"] for c in cards][:4] == ["power", "power-lgbm", "power-mlp", "power-ts"]
    assert {p.stem for p in MODELS.glob("*.md")} == {c["stem"] for c in cards}
    res = build_site(
        Ledger(tmp_path / "l"),
        tmp_path / "site",
        FixedClock(datetime(2026, 11, 13, tzinfo=UTC)),
        models_dir=MODELS,
    )
    page = (res.out_dir / "backtests.html").read_text()
    assert "BACKTEST" in page and 'id="card-power-ts"' in page and "0.1930" in page
    assert load_cards(None) == [] and load_cards(tmp_path / "missing") == []
