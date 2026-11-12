from datetime import UTC, datetime

from factories import forecast, question

from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.site.build import build_site, simple_markdown
from arena.site.linkcheck import check_site

CLOCK = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))


def test_empty_ledger_builds_every_page(tmp_path) -> None:
    res = build_site(Ledger(tmp_path / "l"), tmp_path / "site", CLOCK, tmp_path / "none")
    assert res.pages == ["about.html", "index.html", "methods.html", "status.html"]
    assert check_site(res.out_dir) == []
    for page in res.pages:
        text = (res.out_dir / page).read_text()
        assert "Research project, not advice" in text
        assert "Bundesnetzagentur | SMARD.de" in text
        assert "Rehearsal" in text
        assert 'name="viewport"' in text
        assert "<script" not in text
    css = (res.out_dir / "static" / "style.css").read_text()
    assert "prefers-color-scheme: dark" in css


def test_home_shows_questions_and_forecasts(tmp_path) -> None:
    led = Ledger(tmp_path / "l")
    q = question()
    led.append(layout.questions_path(q.batch_date), [q])
    led.append(layout.forecasts_path(q.batch_date), [forecast(q, "base_rate", 0.61)])
    res = build_site(led, tmp_path / "site", CLOCK, tmp_path / "none")
    home = (res.out_dir / "index.html").read_text()
    assert "0.61" in home and "base_rate" in home and q.text in home


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
