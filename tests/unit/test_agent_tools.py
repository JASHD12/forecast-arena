import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from arena.agent.tools import (
    TOOL_SPECS,
    GdeltBackend,
    Headline,
    StaticNews,
    ToolBox,
    parse_rss,
    wikipedia_summary,
)
from arena.llm.client import ToolCall
from arena.sources.http import HttpClient, HttpRequest, HttpResponse

FIX = Path(__file__).parents[1] / "fixtures" / "agent"
ASOF = datetime(2026, 11, 12, 6, tzinfo=UTC)
CTX = {"domain": "power", "daily": [{"day": f"2026-11-{d:02d}", "mean": d} for d in range(1, 12)]}
NEWS = StaticNews(
    [
        Headline(
            "Strompreis steigt", "example.de", "https://example.de/a", ASOF - timedelta(days=1)
        ),
        Headline(
            "Strompreis future story",
            "example.de",
            "https://example.de/b",
            ASOF + timedelta(hours=1),
        ),
        Headline("Strompreis old", "example.de", "https://example.de/c", ASOF - timedelta(days=20)),
    ]
)
# Synthetic RSS 2.0 sample (not a recorded response): exercises the parser only.
RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Headline one</title><link>https://news.example.org/x</link>
<pubDate>Wed, 11 Nov 2026 08:15:00 GMT</pubDate></item>
<item><title>No date</title><link>https://news.example.org/y</link></item>
</channel></rss>"""


def call(name, **args):
    return ToolCall(f"id-{name}", name, args)


def box(**kw):
    return ToolBox(
        CTX, ASOF, probabilities={"base_rate": {"q1": 0.4}, "ml": {"q1": 0.7}}, news=NEWS, **kw
    )


def test_specs_are_strict_objects() -> None:
    assert {s.name for s in TOOL_SPECS} == {
        "get_series",
        "get_base_rate",
        "get_ml_forecast",
        "search_news",
        "wikipedia_summary",
    }
    assert all(s.input_schema["additionalProperties"] is False for s in TOOL_SPECS)


def test_each_tool() -> None:
    b = box(wiki=lambda t, p: {"title": t, "extract": "lead", "url": f"https://{p}.org/{t}"})
    out, err = b.run(call("get_series", key="daily", lookback_days=3))
    assert not err and len(json.loads(out)["data"]) == 3
    assert (
        json.loads(b.run(call("get_base_rate", question_id="q1"))[0])["data"]["probability"] == 0.4
    )
    assert (
        json.loads(b.run(call("get_ml_forecast", question_id="q1"))[0])["data"]["probability"]
        == 0.7
    )
    news = json.loads(b.run(call("search_news", query="Strompreis", days_back=3))[0])
    assert [h["url"] for h in news["data"]["headlines"]] == ["https://example.de/a"]  # as-of only
    assert b.trace[-1].sources == ["https://example.de/a"]


def test_call_limit() -> None:
    b = box()
    for _ in range(4):
        assert not b.run(call("get_series", key="list"))[1]
    out, err = b.run(call("get_series", key="list"))
    assert err and "limit" in json.loads(out)["error"] and b.calls_left == 0


def test_time_limit() -> None:
    now = [0.0]
    b = box(monotonic=lambda: now[0], time_limit=90)
    assert not b.run(call("get_series", key="list"))[1]
    now[0] = 91.0
    out, err = b.run(call("get_series", key="list"))
    assert err and "time limit" in out


def test_errors_are_results_not_exceptions() -> None:
    b = box()
    out, err = b.run(call("get_series", key="nope"))
    assert err and "KeyError" in out
    assert box().run(call("delete_everything"))[1]
    t = b.compact_trace()
    assert t[0]["ok"] is False and "result" not in t[0]


def test_rss_parser_and_gdelt_request() -> None:
    items = parse_rss(RSS)
    assert len(items) == 1 and items[0].outlet == "news.example.org"
    seen: list[str] = []

    def transport(req: HttpRequest) -> HttpResponse:
        seen.append(req.url)
        return HttpResponse(req.url, 200, {}, RSS)

    sleeps: list[float] = []
    clock = [100.0]
    g = GdeltBackend(
        HttpClient("UA (+x)", transport=transport), monotonic=lambda: clock[0], sleep=sleeps.append
    )
    g.search("strompreis", ASOF - timedelta(days=3), ASOF)
    g.search("strompreis", ASOF - timedelta(days=3), ASOF)
    assert "enddatetime=20261112060000" in seen[0] and "format=rss" in seen[0]
    assert sleeps == [5.0]  # one request every 5 seconds


def test_wikipedia_summary_from_recorded_response() -> None:
    body = (FIX / "wiki_summary_en.json").read_bytes()
    http = HttpClient("UA (+x)", transport=lambda r: HttpResponse(r.url, 200, {}, body))
    s = wikipedia_summary(http, "SS Edmund Fitzgerald", "en.wikipedia")
    assert s["title"] == "SS Edmund Fitzgerald" and "Lake Superior" in s["extract"]
    assert s["url"].endswith("/SS_Edmund_Fitzgerald")


def test_recorded_gdelt_feed_parses() -> None:
    assert parse_rss((FIX / "gdelt_artlist.rss").read_bytes()) == []
