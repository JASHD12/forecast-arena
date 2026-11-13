"""T185: one-row header: primary links plus a "More" disclosure; rehearsal as a pill."""

from datetime import UTC, datetime
from pathlib import Path

from arena.clock import FixedClock
from arena.ledger import Ledger
from arena.site.build import NAV, NAV_MORE, build_site

ROOT = Path(__file__).resolve().parents[2]


def test_every_nav_target_is_built_and_nothing_is_listed_twice(tmp_path) -> None:
    clock = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    res = build_site(Ledger(tmp_path / "l"), tmp_path / "site", clock, ROOT / "site_content")
    hrefs = [h for h, _ in NAV + NAV_MORE]
    assert len(hrefs) == len(set(hrefs)) and len(NAV) <= 7
    for h in hrefs:
        assert (res.out_dir / h).exists(), h
    for h in ("backtests.html", "experiments.html", "evals.html", "llm.html", "data.html"):
        assert h in hrefs  # the strongest pages are reachable from every page
    home = (res.out_dir / "index.html").read_text()
    assert '<details class="nav-more">' in home and 'class="phase-pill"' in home
    assert 'class="banner"' not in home  # the full-width band is gone
    board = (res.out_dir / "leaderboard.html").read_text()
    assert "Rehearsal phase." in board  # the full sentence where it matters
    methods = (res.out_dir / "methods.html").read_text()
    assert 'id="official-start"' in methods
    exp = (res.out_dir / "experiments.html").read_text()
    assert 'class="is-current"' in exp and 'href="experiments.html" aria-current="page"' in exp
