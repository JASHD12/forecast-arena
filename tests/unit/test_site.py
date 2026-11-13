from datetime import UTC, datetime

from factories import forecast, question

from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.site.build import build_site, simple_markdown
from arena.site.linkcheck import check_site

CLOCK = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))


def test_empty_ledger_builds_every_page(tmp_path) -> None:
    res = build_site(Ledger(tmp_path / "l"), tmp_path / "site", CLOCK, tmp_path / "none")
    assert res.pages == [
        "404.html",
        "about.html",
        "api.html",
        "backtests.html",
        "calibration.html",
        "data.html",
        "evals.html",
        "experiments.html",
        "findings.html",
        "forecasters/index.html",
        "guide.html",
        "imprint.html",
        "index.html",
        "leaderboard.html",
        "llm.html",
        "methods.html",
        "play.html",
        "privacy.html",
        "questions/index.html",
        "recruiters.html",
        "stack.html",
        "status.html",
        "topics/index.html",
    ]
    assert check_site(res.out_dir) == []
    for page in res.pages:
        text = (res.out_dir / page).read_text()
        assert "Deutscher Wetterdienst" in text and "European Central Bank" in text
        assert "Research project, not advice" in text
        assert "Bundesnetzagentur | SMARD.de" in text
        assert "Rehearsal" in text
        assert 'name="viewport"' in text
        # every page loads the one self-hosted script (T137), and nothing else
        assert 'static/app.js" defer></script>' in text
    css = (res.out_dir / "static" / "style.css").read_text()
    assert "prefers-color-scheme: dark" in css


def test_home_shows_questions_and_forecasts(tmp_path) -> None:
    led = Ledger(tmp_path / "l")
    q = question()
    led.append(layout.questions_path(q.batch_date), [q])
    led.append(layout.forecasts_path(q.batch_date), [forecast(q, "base_rate", 0.61)])
    res = build_site(led, tmp_path / "site", CLOCK, tmp_path / "none")
    home = (res.out_dir / "index.html").read_text()
    import html as _html

    from arena.site.titles import plain_title

    assert "61%" in home and "width: 61.0%" in home and "Base rate" in home
    assert _html.escape(plain_title(q)) in home
    text = (res.out_dir / "questions" / f"{q.question_id}.html").read_text()
    assert "Exact question:" in text
    assert _html.escape(q.text) in text and _html.escape(q.resolution_rule) in text


def test_about_from_site_content_is_escaped(tmp_path) -> None:
    content = tmp_path / "content"
    content.mkdir()
    (content / "about.md").write_text("# Me\n\nHello <script>x</script> [site](https://e.org)")
    res = build_site(Ledger(tmp_path / "l"), tmp_path / "site", CLOCK, content)
    about = (res.out_dir / "about.html").read_text()
    assert "&lt;script&gt;" in about and '<a href="https://e.org">site</a>' in about
    assert "<script>" not in about


def test_link_check_finds_broken_links(tmp_path) -> None:
    (tmp_path / "index.html").write_text('<a href="missing.html">x</a><a href="#nope">y</a>')
    errors = check_site(tmp_path)
    assert len(errors) == 2


def test_simple_markdown() -> None:
    assert str(simple_markdown("## Title\n\npara")) == "<h3>Title</h3>\n<p>para</p>"


def test_question_pages_rationales_and_changelog(tmp_path) -> None:
    from arena.models import Forecast

    led = Ledger(tmp_path / "l")
    q = question(entity="dewiki.Salpeters%C3%A4ure")
    led.append(layout.questions_path(q.batch_date), [q])
    f = forecast(q, "llm_plain", 0.3)
    f = Forecast(**{**f.model_dump(), "rationale": "Short reason."})
    led.append(layout.forecasts_path(q.batch_date), [f])
    res = build_site(led, tmp_path / "site", CLOCK, tmp_path / "none")
    assert check_site(res.out_dir) == []
    page = (res.out_dir / "questions" / f"{q.question_id}.html").read_text()
    assert "Short reason." in page and "AI-generated" in page
    assert "llm_plain" in (res.out_dir / "methods.html").read_text()


def test_experiments_page_lists_weekly_runs(tmp_path) -> None:
    from pathlib import Path

    led = Ledger(tmp_path / "l")
    fx = Path(__file__).parents[1] / "fixtures" / "weekly" / "2026-11-10-summary.json"
    led.write_raw("models/weekly/2026-11-10-summary.json", fx.read_bytes())
    res = build_site(led, tmp_path / "site", CLOCK, tmp_path / "none")
    page = (res.out_dir / "experiments.html").read_text()
    assert "2026-11-10" in page and "power" in page and "first model" in page
    assert 'href="experiments.html"' in (res.out_dir / "status.html").read_text()
    assert check_site(res.out_dir) == []


def test_data_dictionary_documents_every_exported_column() -> None:
    from arena.analytics.sql import COLUMN_DOCS, TABLES, column_types

    types = column_types()
    assert set(COLUMN_DOCS) == set(TABLES)
    for table in TABLES:
        assert set(COLUMN_DOCS[table]) == set(types[table]), table
        assert all(len(v) > 10 for v in COLUMN_DOCS[table].values())
