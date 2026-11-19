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


def test_official_start_rule_names_the_not_before_date() -> None:
    """T200: the rehearsal text must not promise an automatic start."""
    from arena.site.build import START_RULE

    assert "not before a start date" in START_RULE
    assert "automatically" not in START_RULE


def test_social_preview_and_base_rate_note(tmp_path) -> None:
    """T214 / T221: og/twitter meta point at a real 1200x630 image; Methods explains base rates."""
    import struct
    from datetime import UTC, datetime
    from pathlib import Path

    from arena.clock import FixedClock
    from arena.ledger import Ledger
    from arena.site.build import build_site

    root = Path(__file__).resolve().parents[2]
    res = build_site(
        Ledger(tmp_path / "l"),
        tmp_path / "site",
        FixedClock(datetime(2026, 11, 13, tzinfo=UTC)),
        root / "site_content",
    )
    home = (res.out_dir / "index.html").read_text()
    assert 'property="og:image" content="' in home and "static/og.png" in home
    assert 'name="twitter:card" content="summary_large_image"' in home
    png = (res.out_dir / "static" / "og.png").read_bytes()
    assert struct.unpack(">II", png[16:24]) == (1200, 630)
    methods = (res.out_dir / "methods.html").read_text()
    assert "Why a base rate can score worse than 0.25" in methods
