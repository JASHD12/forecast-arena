from datetime import UTC, date, datetime

import pytest
from wikimedia_fixtures import fixture_client

from arena.sources.wikimedia import (
    WikimediaError,
    encode_title,
    instance_of,
    pageviews_available_at,
    parse_per_article,
    parse_top,
    person_titles,
)


def test_title_encoding() -> None:
    assert encode_title("AC/DC") == "AC%2FDC"
    assert encode_title("Rudolf Höß") == "Rudolf_H%C3%B6%C3%9F"
    assert encode_title("The_Zone_of_Interest_(Film)") == "The_Zone_of_Interest_%28Film%29"


def test_top_lists_and_unpublished_day(tmp_path) -> None:
    client, transport = fixture_client(cache_dir=tmp_path)
    de = client.top("de.wikipedia", date(2026, 11, 10))
    assert de is not None and len(de) == 1000 and de[0].rank == 1
    assert de[4].article == "Rudolf_Höß"
    assert client.top("de.wikipedia", date(2026, 11, 13)) is None  # lag: not yet published
    n = len(transport.urls)
    assert client.top("de.wikipedia", date(2026, 11, 10)) == de  # served from cache
    assert len(transport.urls) == n
    en = client.top("en.wikipedia", date(2026, 11, 10))
    assert en is not None and en[4].article == "Russell_Brand"


def test_per_article_series_and_missing_article() -> None:
    client, _ = fixture_client()
    url, sha, series = client.per_article(
        "de.wikipedia", "Rudolf_Höß", date(2026, 8, 1), date(2026, 11, 11)
    )
    assert len(series) == 103 and series[date(2026, 11, 1)] == 775 and len(sha) == 64
    assert "Rudolf_H%C3%B6%C3%9F" in url
    _, _, slash = client.per_article("en.wikipedia", "AC/DC", date(2026, 11, 1), date(2026, 11, 11))
    assert len(slash) == 11
    _, _, gone = client.per_article(
        "de.wikipedia", "Gibt_es_nicht_xyz_123", date(2026, 11, 1), date(2026, 11, 11)
    )
    assert gone == {}


def test_person_check_fails_closed() -> None:
    client, _ = fixture_client()
    titles = ["Ilse_Aigner", "The_Zone_of_Interest_(Film)", "Rudolf_Höß", "Gibtsnicht_xyz"]
    p31 = client.instance_of("de.wikipedia", titles)
    excluded = person_titles(titles, p31)
    assert excluded == {"Ilse_Aigner", "Rudolf_Höß", "Gibtsnicht_xyz"}
    assert person_titles(["Unknown"], {}) == {"Unknown"}


def test_availability_rule() -> None:
    assert pageviews_available_at(date(2026, 11, 10)) == datetime(2026, 11, 12, tzinfo=UTC)


@pytest.mark.parametrize("fn", [parse_top, parse_per_article, instance_of])
def test_malformed(fn) -> None:
    with pytest.raises(WikimediaError):
        fn({"nope": 1})


def test_article_series_and_p31_are_cached(tmp_path) -> None:
    client, transport = fixture_client(cache_dir=tmp_path)
    args = ("de.wikipedia", "Rudolf_Höß", date(2026, 8, 1), date(2026, 11, 11))
    first = client.per_article(*args)
    n = len(transport.urls)
    assert client.per_article(*args) == first and len(transport.urls) == n
    titles = ["Ilse_Aigner", "The_Zone_of_Interest_(Film)", "Rudolf_Höß", "Gibtsnicht_xyz"]
    a = client.instance_of("de.wikipedia", titles)
    n = len(transport.urls)
    b = client.instance_of("de.wikipedia", titles[:3])
    assert len(transport.urls) == n  # all three found titles came from the cache
    assert {k: a[k] for k in b} == b
