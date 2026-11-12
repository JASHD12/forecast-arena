"""Serve recorded Bright Sky fixtures (tests/fixtures/brightsky) through HttpClient."""

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from arena.sources.brightsky import BrightSkyClient
from arena.sources.http import HttpClient, HttpRequest, HttpResponse

FIXTURES = Path(__file__).parents[1] / "fixtures" / "brightsky"


class BrightSkyFixtureTransport:
    """obs_<station>_<day>.json for past days, fc_<station>_<day>.json for forecasts."""

    def __init__(self, root: Path = FIXTURES) -> None:
        self.root = root
        self.urls: list[str] = []

    def __call__(self, req: HttpRequest) -> HttpResponse:
        self.urls.append(req.url)
        q = parse_qs(urlsplit(req.url).query)
        station, day = q["dwd_station_id"][0], q["date"][0][:10]
        for prefix in ("obs", "fc"):
            path = self.root / f"{prefix}_{station}_{day}.json"
            if path.exists():
                return HttpResponse(req.url, 200, {}, path.read_bytes())
        return HttpResponse(req.url, 404, {}, b"")


def fixture_client() -> tuple[BrightSkyClient, BrightSkyFixtureTransport]:
    t = BrightSkyFixtureTransport()
    return BrightSkyClient(HttpClient("ForecastArena/test (+x)", transport=t)), t
