"""T182: the post-deploy smoke test, against the offline demo build served locally."""

import functools
import http.server
import importlib.util
import shutil
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("smoke_site", ROOT / "scripts" / "smoke_site.py")
assert spec and spec.loader
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


@pytest.fixture
def served(tmp_path):
    """The e2e site build (make site-e2e), copied and served on localhost."""
    src = ROOT / "_site_e2e"
    if not (src / "index.html").exists():
        pytest.skip("run `make site-e2e` first")
    site = tmp_path / "site"
    shutil.copytree(src, site)

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a) -> None:
            pass

    handler = functools.partial(Quiet, directory=str(site))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/", site
    srv.shutdown()


def built_time(site: Path) -> datetime:

    m = smoke.BUILT.search((site / "index.html").read_text())
    assert m
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


def test_a_healthy_site_passes_and_a_stale_one_does_not(served) -> None:
    url, site = served
    now = built_time(site) + timedelta(hours=1)
    assert smoke.check(url, now) == []
    problems = smoke.check(url, now + timedelta(hours=30))
    assert len(problems) == 1 and "older than" in problems[0]


def test_missing_pages_assets_and_data_are_reported(served) -> None:
    url, site = served
    now = built_time(site) + timedelta(hours=1)
    (site / "leaderboard.html").unlink()
    (site / "static" / "app.js").unlink()
    (site / "data" / "game.json").unlink()
    problems = " | ".join(smoke.check(url, now))
    assert "leaderboard.html: HTTP 404" in problems
    assert "static/app.js: HTTP 404" in problems and "data/game.json: HTTP 404" in problems
    assert "asset static/app.js: HTTP 404" in problems  # referenced by every page


def test_a_page_without_the_csp_or_the_name_is_reported(served) -> None:
    url, site = served
    now = built_time(site) + timedelta(hours=1)
    (site / "play.html").write_text("<html><body>hello</body></html>")
    problems = " | ".join(smoke.check(url, now))
    assert "play.html: does not look like a Forecast Arena page" in problems
    assert "play.html: no Content-Security-Policy meta tag" in problems
