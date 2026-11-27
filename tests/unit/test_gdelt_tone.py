"""GDELT tone source (T371): parsers against the real recorded responses, as-of rule, client."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from arena.sources import gdelt_tone as G
from arena.sources.http import HttpClient, HttpRequest, HttpResponse

FIX = Path(__file__).parents[1] / "fixtures" / "gdelt"
TONE = FIX / "bitcoin_timelinetone_20261101_20261110.json"
VOL = FIX / "bitcoin_timelinevolraw_20261101_20261110.json"


def _load(p: Path) -> object:
    return json.loads(p.read_text("utf-8"))


def test_fixtures_match_their_provenance_hashes() -> None:
    import hashlib

    prov = {r["mode"]: r["sha256"] for r in _load(FIX / "provenance.json")}  # type: ignore[attr-defined]
    assert hashlib.sha256(TONE.read_bytes()).hexdigest() == prov["TimelineTone"]
    assert hashlib.sha256(VOL.read_bytes()).hexdigest() == prov["TimelineVolRaw"]


def test_parse_tone_real_response() -> None:
    tone = G.parse_tone(_load(TONE))
    assert len(tone) == 8 and min(tone) == date(2026, 11, 3) and max(tone) == date(2026, 11, 10)
    assert tone[date(2026, 11, 3)] == pytest.approx(-3.0297)
    assert tone[date(2026, 11, 8)] == pytest.approx(0.9559)


def test_parse_counts_real_response() -> None:
    count, total = G.parse_counts(_load(VOL))
    assert count[date(2026, 11, 6)] == 35 and total[date(2026, 11, 6)] == 55749
    assert set(count) == set(total) and len(count) == 8


def test_missing_days_are_not_filled() -> None:
    assert date(2026, 11, 1) not in G.parse_tone(_load(TONE))


def test_empty_timeline_is_empty_not_an_error() -> None:
    assert G.parse_tone({"query_details": {}, "timeline": []}) == {}


@pytest.mark.parametrize("bad", [{}, {"timeline": [{"series": "Other", "data": []}]}, None])
def test_malformed_payloads_raise(bad: object) -> None:
    with pytest.raises(G.GdeltError):
        G.parse_tone(bad)


def test_implausible_counts_raise() -> None:
    bad = {
        "timeline": [
            {
                "series": G.COUNT_SERIES,
                "data": [{"date": "20261103T000000Z", "value": 5, "norm": 2}],
            }
        ]
    }
    with pytest.raises(G.GdeltError):
        G.parse_counts(bad)


def test_as_of_rule_uses_only_days_that_ended_plus_the_lag() -> None:
    assert G.available_at(date(2026, 11, 3)) == datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    # at 09:30 UTC on 5 Nov the latest known day is 3 Nov (4 Nov is known from 5 Nov 12:00)
    asof = datetime(2026, 11, 5, 9, 30, tzinfo=UTC)
    assert G.known_days(asof) == date(2026, 11, 3)
    tone = G.parse_tone(_load(TONE))
    seen = G.as_of(tone, asof)
    assert max(seen) == date(2026, 11, 3) and date(2026, 11, 4) not in seen
    after = G.as_of(tone, datetime(2026, 11, 5, 12, 0, tzinfo=UTC))
    assert max(after) == date(2026, 11, 4)


def test_known_days_needs_an_aware_time() -> None:
    with pytest.raises(ValueError):
        G.known_days(datetime(2026, 11, 5, 9, 30))


def test_timeline_url_parameters() -> None:
    url, params = G.timeline_url("solana", "TimelineTone", date(2026, 11, 1), date(2026, 11, 10))
    assert url == G.BASE and params["query"] == "solana crypto sourcelang:english"
    assert params["startdatetime"] == "20261101000000" and params["enddatetime"] == "20261110235959"
    with pytest.raises(G.GdeltError):
        G.timeline_url("dogecoin", "TimelineTone", date(2026, 11, 1), date(2026, 11, 2))


def test_client_fetches_both_modes_and_waits_between_requests() -> None:
    sleeps: list[float] = []
    seen: list[str] = []

    def transport(req: HttpRequest) -> HttpResponse:
        seen.append(req.url)
        body = (TONE if "TimelineTone" in req.url else VOL).read_bytes()
        return HttpResponse(req.url, 200, {}, body)

    http = HttpClient("test-agent", transport=transport, sleep=lambda s: None)
    client = G.GdeltClient(http, pause=5.5, sleep=sleeps.append)
    news = client.daily("bitcoin", date(2026, 11, 1), date(2026, 11, 10))
    assert len(seen) == 2 and sleeps == [5.5]
    assert (
        news.tone[date(2026, 11, 3)] == pytest.approx(-3.0297)
        and news.count[date(2026, 11, 6)] == 35
    )
    assert len(news.sha256) == 2 and "mode=TimelineTone" in news.urls[0]


def test_client_rejects_non_json() -> None:
    def transport(req: HttpRequest) -> HttpResponse:
        return HttpResponse(req.url, 200, {}, b"Your query was too short.")

    client = G.GdeltClient(HttpClient("t", transport=transport), pause=0, sleep=lambda s: None)
    with pytest.raises(G.GdeltError):
        client.daily("bitcoin", date(2026, 11, 1), date(2026, 11, 10))
