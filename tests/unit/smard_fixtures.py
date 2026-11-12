"""Serve recorded SMARD fixtures through the real HttpClient (no network)."""

from pathlib import Path

from arena.sources.http import HttpClient, HttpRequest, HttpResponse
from arena.sources.smard import BASE, SmardClient

FIXTURES = Path(__file__).parents[1] / "fixtures" / "smard"


class SmardFixtureTransport:
    """Maps SMARD URLs to files in tests/fixtures/smard; anything else is a 404."""

    def __init__(self, root: Path = FIXTURES) -> None:
        self.root = root
        self.urls: list[str] = []

    def __call__(self, req: HttpRequest) -> HttpResponse:
        self.urls.append(req.url)
        name = req.url.removeprefix(BASE + "/").split("/")[-1]
        if name.startswith("index_"):
            filt = req.url.removeprefix(BASE + "/").split("/")[0]
            name = f"index_{filt}_DE_hour.json"
        path = self.root / name
        if not path.exists():
            return HttpResponse(req.url, 404, {}, b"")
        return HttpResponse(req.url, 200, {}, path.read_bytes())


def fixture_client(**kw) -> tuple[SmardClient, SmardFixtureTransport]:
    transport = SmardFixtureTransport()
    http = HttpClient("ForecastArena/test (+x)", transport=transport, sleep=lambda s: None)
    return SmardClient(http, **kw), transport
