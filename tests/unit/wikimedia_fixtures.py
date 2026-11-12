"""Replay recorded Wikimedia/Wikidata responses (tests/fixtures/wikimedia/index.json)."""

import gzip
import json
from pathlib import Path

from arena.sources.http import HttpClient, HttpRequest, HttpResponse
from arena.sources.wikimedia import WikimediaClient

FIXTURES = Path(__file__).parents[1] / "fixtures" / "wikimedia"


class WikimediaFixtureTransport:
    def __init__(self) -> None:
        self.index = json.loads((FIXTURES / "index.json").read_text(encoding="utf-8"))
        self.urls: list[str] = []

    def __call__(self, req: HttpRequest) -> HttpResponse:
        self.urls.append(req.url)
        name = self.index.get(req.url)
        if name is None:
            return HttpResponse(req.url, 404, {}, b"")
        rec = json.loads(gzip.decompress((FIXTURES / name).read_bytes()))
        return HttpResponse(req.url, rec["status"], {}, rec["body"].encode())


def fixture_client(cache_dir=None) -> tuple[WikimediaClient, WikimediaFixtureTransport]:
    t = WikimediaFixtureTransport()
    http = HttpClient("ForecastArena/test (+x)", transport=t, sleep=lambda s: None)
    return WikimediaClient(http, cache_dir=cache_dir), t
