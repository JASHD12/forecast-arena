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
    "notebooks",  # executed by `make notebook` in the CI a11y job
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


def test_role_cards_link_to_real_pages_and_code(tmp_path) -> None:
    """P2: every role-card link resolves in the built site or in the repository."""
    from arena.site.recruiters import ROLE_PATHS

    clock = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    res = build_site(Ledger(tmp_path / "l"), tmp_path / "site", clock, ROOT / "site_content")
    page = (res.out_dir / "recruiters.html").read_text()
    assert len(ROLE_PATHS) == 3
    for role, _, links in ROLE_PATHS:
        assert role in page and len(links) >= 2
        for _, target, is_repo in links:
            if is_repo:
                assert (ROOT / target).is_file(), target
                assert any(target.startswith(c + "/") for c in CI_COVERED), target
            else:
                assert (res.out_dir / target.split("#")[0]).exists(), target
                assert f'href="{target}"' in page


def test_first_screen_result_comes_from_the_model_card(tmp_path) -> None:
    """P1: kicker, headline, a generated result and a button; no personal facts shown yet."""
    from arena.site.cards_page import headline_backtest

    bt = headline_backtest(ROOT / "docs" / "models")
    assert bt is not None
    ml = dict((f, v) for f, v, _ in bt["rows"])
    clock = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    res = build_site(
        Ledger(tmp_path / "l"),
        tmp_path / "site",
        clock,
        ROOT / "site_content",
        models_dir=ROOT / "docs" / "models",
    )
    page = (res.out_dir / "recruiters.html").read_text()
    assert "I build forecasting systems and test them honestly." in page
    assert f"Brier {ml['ml']} vs {ml['persistence']} over {bt['days']} backtest days" in page
    vp = bt["vs_persistence"]
    assert f"paired difference {vp['diff']} {vp['interval']}, excludes zero" in page
    assert "Werkstudent AI / Machine Learning / Data Science" in page
    assert "Download CV" not in page and "LinkedIn" not in page  # H16 facts absent: omitted


def test_owner_facts_are_shown_only_when_valid(tmp_path) -> None:
    """P1: facts from recruiter_facts.json appear; drafts, empty values and unsafe links do not."""
    import json

    from arena.site.recruiters import load_facts

    assert load_facts(None) == {} and load_facts(tmp_path) == {}
    (tmp_path / "recruiter_facts.json").write_text(
        json.dumps(
            {
                "city": "Berlin",
                "availability": "20 h/week from 2027-01-04",
                "linkedin": "javascript:alert(1)",
                "cv_url": "https://example.org/cv.pdf",
                "email": "[FILL IN]",
                "languages": " ",
            }
        )
    )
    facts = load_facts(tmp_path)
    assert facts == {
        "city": "Berlin",
        "availability": "20 h/week from 2027-01-04",
        "cv_url": "https://example.org/cv.pdf",
    }
    content = tmp_path / "c"
    content.mkdir()
    (content / "recruiter_facts.json").write_text((tmp_path / "recruiter_facts.json").read_text())
    clock = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    res = build_site(Ledger(tmp_path / "l"), tmp_path / "site", clock, content)
    page = (res.out_dir / "recruiters.html").read_text()
    assert "· Berlin · 20 h/week from 2027-01-04" in page
    assert 'href="https://example.org/cv.pdf">Download CV (PDF)' in page
    assert "javascript:" not in page
