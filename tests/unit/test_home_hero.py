"""T186: the home hero's BACKTEST card and the recruiter page are generated, not typed."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from arena.clock import FixedClock
from arena.ledger import Ledger
from arena.site.build import build_site, json_validity_change
from arena.site.cards_page import headline_backtest

ROOT = Path(__file__).resolve().parents[2]
MODELS, EVALS = ROOT / "docs" / "models", ROOT / "evals" / "results"


def _site(tmp_path):
    clock = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    return build_site(
        Ledger(tmp_path / "l"),
        tmp_path / "site",
        clock,
        ROOT / "site_content",
        models_dir=MODELS,
        evals_dir=EVALS,
    ).out_dir


def test_backtest_card_matches_the_model_card(tmp_path) -> None:
    card = (MODELS / "power.md").read_text()
    bt = headline_backtest(MODELS)
    assert bt is not None and bt["days"] == 365 and bt["supported"]
    for fid, v, _ in bt["rows"]:
        assert re.search(rf"^\| {fid} \| \d+ \| {re.escape(v)} \|", card, re.M), fid
    assert f"| ml - base_rate | {bt['diff']} | {bt['interval']} |" in card
    home = (_site(tmp_path) / "index.html").read_text()
    assert ">backtest</span>" in home and bt["diff"] in home and "Not the live record" in home
    assert "joining soon" not in home
    assert headline_backtest(tmp_path / "missing") is None


def test_recruiter_page_is_honest_and_computed(tmp_path) -> None:
    page = (_site(tmp_path) / "recruiters.html").read_text()
    assert "by one person" not in page and "AI coding agent" in page
    assert "Five things worth 30 seconds" in page and 'href="guide.html#verify"' in page
    runs = [json.loads(p.read_text()) for p in EVALS.glob("eval-*.json")]
    ch = json_validity_change(runs)
    assert ch is not None and f"from {ch['before']} to {ch['after']}" in page
    assert json_validity_change(runs[:1]) is None
