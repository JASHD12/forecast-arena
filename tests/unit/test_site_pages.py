"""Pages added on the owner's request (2026-11-12): guide, privacy, imprint, 404, feed,
topic filters, per-question scores, and the no-third-party-requests rule."""

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from html.parser import HTMLParser

from factories import B, forecast, question

from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.models import Evidence, Resolution
from arena.site.build import build_site, question_scores

CLOCK = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))


def _site(tmp_path, content=None):
    led = Ledger(tmp_path / "l")
    q = question()
    led.append(layout.questions_path(q.batch_date), [q])
    led.append(
        layout.forecasts_path(q.batch_date),
        [forecast(q, "base_rate", 0.61), forecast(q, "llm_context", 0.2)],
    )
    res = Resolution(
        question_id=q.question_id,
        outcome=0,
        observed_value=70.0,
        resolved_at=datetime(2026, 11, 14, 12, tzinfo=UTC),
        evidence=Evidence(source_url="https://www.smard.de/x", snapshot_sha256="a" * 64,
                          values_used={}),
    )  # fmt: skip
    led.append(layout.resolutions_path(B), [res])
    return q, build_site(led, tmp_path / "site", CLOCK, content or tmp_path / "none",
                         site_url="https://example.org/arena")  # fmt: skip


class _Refs(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.loaded: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "img", "iframe", "video", "audio", "source") and a.get("src"):
            self.loaded.append(a["src"])
        if tag == "link" and a.get("rel") in ("stylesheet", "icon", "preload") and a.get("href"):
            self.loaded.append(a["href"])
        if tag == "script":
            self.loaded.append("<script>")


def test_new_pages_exist_and_are_linked_from_every_page(tmp_path) -> None:
    _, res = _site(tmp_path)
    for name in ("guide.html", "privacy.html", "imprint.html", "404.html", "feed.xml",
                 "static/favicon.svg", "questions/topic-power.html"):  # fmt: skip
        assert (res.out_dir / name).is_file(), name
    for page in res.out_dir.rglob("*.html"):
        text = page.read_text()
        assert 'imprint.html"' in text and 'privacy.html"' in text, page
        assert "AI disclosure" in text and "not advice" in text, page


def test_no_third_party_requests_no_scripts_no_cookies(tmp_path) -> None:
    _, res = _site(tmp_path)
    for page in res.out_dir.rglob("*.html"):
        p = _Refs()
        p.feed(page.read_text())
        for ref in p.loaded:
            assert ref != "<script>", f"script in {page}"
            assert not re.match(r"^(https?:)?//", ref), f"{page} loads {ref}"
    css = (res.out_dir / "static" / "style.css").read_text()
    assert "@import" not in css and "url(http" not in css and "fonts.g" not in css


def test_legal_pages_pending_until_owner_writes_them(tmp_path) -> None:
    _, res = _site(tmp_path)
    assert "Pending" in (res.out_dir / "imprint.html").read_text()
    privacy = (res.out_dir / "privacy.html").read_text()
    assert "Pending" in privacy and "GitHub Pages" in privacy and "IP address" in privacy
    content = tmp_path / "content"
    content.mkdir()
    (content / "imprint.md").write_text("# Provider\n\nJane Example, Somewhere 1")
    (content / "privacy.md").write_text("Controller: Jane Example")
    _, res2 = _site(tmp_path / "x", content)
    assert "Jane Example, Somewhere 1" in (res2.out_dir / "imprint.html").read_text()
    assert "Controller: Jane Example" in (res2.out_dir / "privacy.html").read_text()


def test_feed_is_valid_atom_with_absolute_links(tmp_path) -> None:
    _, res = _site(tmp_path)
    root = ET.fromstring((res.out_dir / "feed.xml").read_text())
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entries = root.findall("a:entry", ns)
    assert len(entries) == 1
    assert root.find("a:link[@rel='self']", ns).get("href") == "https://example.org/arena/feed.xml"
    assert "https://example.org/arena/questions/" in entries[0].find("a:content", ns).text


def test_404_uses_absolute_base(tmp_path) -> None:
    _, res = _site(tmp_path)
    assert '<base href="https://example.org/arena/">' in (res.out_dir / "404.html").read_text()


def test_question_page_ranks_closest_first(tmp_path) -> None:
    q, res = _site(tmp_path)
    page = (res.out_dir / "questions" / f"{q.question_id}.html").read_text()
    assert "Who was closest?" in page and "NO" in page
    assert page.index("AI with data") < page.index("Base rate")  # 0.2 beats 0.61 on a NO
    rows = question_scores([forecast(q, "a", 0.9), forecast(q, "b", 0.1)], 1)
    assert [r["f"].forecaster_id for r in rows] == ["a", "b"]
    assert rows[0]["brier"] == (0.9 - 1) ** 2
    assert all(r["brier"] is None for r in question_scores([forecast(q, "a", 0.9)], None))


def test_stack_page_reads_versions_from_environment_and_ledger(tmp_path) -> None:
    from importlib.metadata import version

    from arena.site.build import live_versions

    _, res = _site(tmp_path)
    page = (res.out_dir / "stack.html").read_text()
    assert version("scikit-learn") in page and version("anthropic") in page
    assert "HistGradientBoostingRegressor" in page and "Running right now" in page

    from types import SimpleNamespace

    f = forecast(question(), "llm_context", 0.3).model_copy(
        update={"forecaster_version": "claude-opus-5-5|prompt-v1-abc"}
    )
    assert live_versions(SimpleNamespace(forecasts=[f])) == [
        {
            "id": "llm_context",
            "version": "claude-opus-5-5|prompt-v1-abc",
            "model": "claude-opus-5-5",
        }
    ]


def test_home_race_spotlight_and_honest_ml_status(tmp_path) -> None:
    from types import SimpleNamespace

    from arena.site.build import featured_row, race_data
    from arena.site.charts import race_svg

    _, res = _site(tmp_path)
    home = (res.out_dir / "index.html").read_text()
    assert "Biggest disagreement today" in home and "joining soon" in home
    rows = [{"pn": {"a": 0.1, "b": 0.9}, "q": 1}, {"pn": {"a": 0.5, "b": 0.6}, "q": 2}]
    assert featured_row(rows)["q"] == 1 and featured_row([]) is None
    d = datetime(2026, 11, 1, tzinfo=UTC).date()
    sc = [
        SimpleNamespace(question_id=q, forecaster_id=f, batch_date=d, probability=p, outcome=1)
        for q in ("q1", "q2")
        for f, p in (("base_rate", 0.5), ("ml", 0.9))
    ] + [SimpleNamespace(question_id="q3", forecaster_id="ml", batch_date=d, probability=0.1,
                         outcome=1)]  # fmt: skip
    r = race_data(sc)
    assert r["n"] == 2  # q3 is not in the common set
    assert r["series"]["base_rate"] == [("2026-11-01", 0.25)]
    assert abs(r["series"]["ml"][0][1] - 0.01) < 1e-12
    svg = race_svg(r["series"], {"ml": "ML model"}, r["days"])
    assert "<title>ML model: 0.010 after 2026-11-01</title>" in svg and "coin flip" in svg
