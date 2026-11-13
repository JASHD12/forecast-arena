"""Streamlit dashboard (T143): AppTest smoke test on the offline e2e export."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "apps" / "dashboard" / "streamlit_app.py"


def _export(tmp_path) -> Path:
    """Build a tiny site from the e2e schedule and return its data folder."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
    from datetime import UTC, datetime

    from test_e2e import run_schedule

    from arena.clock import FixedClock
    from arena.site.build import build_site

    led = run_schedule(tmp_path / "ledger")
    res = build_site(led, tmp_path / "site", FixedClock(datetime(2026, 10, 27, tzinfo=UTC)))
    return res.out_dir / "data"


def test_dashboard_renders_and_filters(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ARENA_DATA_DIR", str(_export(tmp_path)))
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert "Forecast Arena" in at.title[0].value
    assert len(at.dataframe) == 3 and len(at.metric) == 3
    board = at.dataframe[0].value
    assert {"forecaster_id", "n", "brier"} <= set(board.columns)
    assert (board["brier"].between(0, 1)).all()
    at.multiselect[1].set_value(["base_rate"]).run()  # filter to one forecaster
    assert not at.exception
    assert list(at.dataframe[0].value["forecaster_id"]) == ["base_rate"]


def test_site_links_the_dashboard_only_when_configured(tmp_path) -> None:
    from datetime import UTC, datetime

    from arena.clock import FixedClock
    from arena.ledger import Ledger
    from arena.site.build import build_site

    clk = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    off = build_site(Ledger(tmp_path / "a"), tmp_path / "s1", clk)
    assert "interactive dashboard" not in (off.out_dir / "data.html").read_text()
    on = build_site(
        Ledger(tmp_path / "b"), tmp_path / "s2", clk, dashboard_url="https://example.streamlit.app"
    )
    assert 'href="https://example.streamlit.app"' in (on.out_dir / "data.html").read_text()
