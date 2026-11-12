import gzip
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from arena.sources.ecb import (
    EcbClient,
    EcbError,
    easter,
    fixing_available_at,
    is_publication_day,
    next_publication_day,
    parse_csv,
)
from arena.sources.http import HttpClient, HttpRequest, HttpResponse

FIX = Path(__file__).parents[1] / "fixtures" / "ecb" / "exr_usd_jpy_2019-01-01.csv.gz"


def client() -> tuple[EcbClient, list[str]]:
    urls: list[str] = []

    def t(req: HttpRequest) -> HttpResponse:
        urls.append(req.url)
        return HttpResponse(req.url, 200, {}, gzip.decompress(FIX.read_bytes()))

    return EcbClient(HttpClient("ForecastArena/test (+x)", transport=t)), urls


def test_fixture_parses_and_calendar_matches_every_weekday() -> None:
    c, urls = client()
    r = c.rates(["USD", "JPY"], date(2019, 1, 1))
    assert "D.USD+JPY.EUR.SP00.A" in urls[0] and len(r.sha256) == 64
    usd = r.rates["USD"]
    assert usd[date(2026, 11, 11)] == 1.1127 and r.rates["JPY"][date(2026, 11, 11)] == 177.18
    d, last = date(2019, 1, 1), max(usd)
    while d <= last:
        if d.weekday() < 5:
            assert (d in usd) == is_publication_day(d), d
        d = date.fromordinal(d.toordinal() + 1)


def test_calendar() -> None:
    assert easter(2026) == date(2026, 4, 5) and easter(2027) == date(2027, 3, 28)
    assert not is_publication_day(date(2026, 4, 3))  # Good Friday
    assert not is_publication_day(date(2026, 12, 26)) and not is_publication_day(date(2026, 11, 14))
    assert next_publication_day(date(2026, 11, 13)) == date(2026, 11, 16)  # Friday -> Monday
    assert next_publication_day(date(2026, 12, 24)) == date(2026, 12, 28)
    assert next_publication_day(date(2026, 4, 2)) == date(2026, 4, 7)


def test_availability() -> None:
    assert fixing_available_at(date(2026, 11, 11)) == datetime(2026, 11, 11, 16, tzinfo=UTC)


def test_malformed() -> None:
    with pytest.raises(EcbError):
        parse_csv("<html>error</html>")
    assert parse_csv("") == {}
