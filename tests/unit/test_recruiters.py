"""'For recruiters' page (T140): every technology named links to code CI runs."""

from datetime import UTC, datetime
from pathlib import Path

from arena.clock import FixedClock
from arena.ledger import Ledger
from arena.site.build import build_site
from arena.site.recruiters import PROOFS

ROOT = Path(__file__).resolve().parents[2]
#: Folders and files exercised by CI (make check, a11y, notebook, docker, kind, dbt, airflow).
CI_COVERED = (
    "src/arena",
    "tests",
    "Makefile",
    "analytics/dbt",
    "apps/dashboard",
    "tools/a11y",
    "Dockerfile",
    "deploy/k8s",
    "orchestration/airflow",
    ".github/workflows",
)


def test_every_named_path_exists_and_is_run_by_ci() -> None:
    for skill, _, _, paths in PROOFS:
        assert paths, skill
        for p in paths:
            assert (ROOT / p).exists(), (skill, p)
            assert any(
                p == c or p.startswith(c + "/") or c.startswith(p + "/") for c in CI_COVERED
            ), (skill, p)


def test_page_links_resolve_and_placeholder_stays_private(tmp_path) -> None:
    clock = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    res = build_site(Ledger(tmp_path / "l"), tmp_path / "site", clock, ROOT / "site_content")
    page = (res.out_dir / "recruiters.html").read_text()
    for _, _, link, _ in PROOFS:
        if link:
            assert (res.out_dir / link.split("#")[0]).exists(), link
            assert f'href="{link}"' in page
    assert "FILL IN" not in page and "About me" not in page  # H16 not done yet
    assert 'href="recruiters.html"' in (res.out_dir / "index.html").read_text()  # in the nav


def test_german_page_language_and_link(tmp_path) -> None:
    clock = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    res = build_site(Ledger(tmp_path / "l"), tmp_path / "site", clock)
    de = (res.out_dir / "de.html").read_text()
    assert '<html lang="de">' in de and "Forschungsprojekt, keine Beratung" in de
    assert '<header class="site-header" lang="en">' in de  # the shared English chrome
    home = (res.out_dir / "index.html").read_text()
    assert '<html lang="en">' in home and 'hreflang="de"' in home
