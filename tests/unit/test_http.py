import gzip
from pathlib import Path

import pytest

from arena.config import Settings
from arena.sources.http import HttpClient, HttpError, HttpRequest, HttpResponse


class Fake:
    def __init__(self, *outcomes) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[HttpRequest] = []

    def __call__(self, req: HttpRequest) -> HttpResponse:
        self.requests.append(req)
        out = self.outcomes.pop(0)
        if isinstance(out, BaseException):
            raise out
        status, body, headers = out
        return HttpResponse(req.url, status, headers, body)


def client(fake: Fake, sleeps: list, **kw) -> HttpClient:
    return HttpClient("ForecastArena/test (+x)", transport=fake, sleep=sleeps.append, **kw)


def test_user_agent_sent_and_required() -> None:
    fake, sleeps = Fake((200, b"{}", {})), []
    ua = Settings.from_env({"ARENA_CONTACT": "me@example.org"}).user_agent()
    HttpClient(ua, transport=fake, sleep=sleeps.append).get("https://x.test/a", {"q": "1 2"})
    assert fake.requests[0].headers["User-Agent"] == ua
    assert fake.requests[0].url == "https://x.test/a?q=1+2"
    with pytest.raises(ValueError):
        HttpClient(" ")


def test_retries_5xx_then_succeeds_with_backoff() -> None:
    fake, sleeps = Fake((503, b"", {}), (502, b"", {}), (200, b'{"ok":1}', {})), []
    resp = client(fake, sleeps).get("https://x.test")
    assert resp.json() == {"ok": 1}
    assert sleeps == [1.0, 2.0]


def test_timeout_retried_then_gives_up() -> None:
    fake = Fake(*(TimeoutError("slow") for _ in range(4)))
    sleeps: list = []
    with pytest.raises(HttpError, match="after 4 attempts: TimeoutError"):
        client(fake, sleeps, retries=3).get("https://x.test")
    assert len(fake.requests) == 4


def test_retry_after_respected_and_capped() -> None:
    fake, sleeps = Fake((429, b"", {"retry-after": "500"}), (200, b"{}", {})), []
    client(fake, sleeps, max_wait=30).get("https://x.test")
    assert sleeps == [30]


def test_client_errors_not_retried() -> None:
    fake, sleeps = Fake((404, b"", {})), []
    with pytest.raises(HttpError) as exc:
        client(fake, sleeps).get("https://x.test")
    assert exc.value.status == 404 and len(fake.requests) == 1


def test_gzip_and_snapshot(tmp_path: Path) -> None:
    body = gzip.compress(b'{"a":1}')
    fake, sleeps = Fake((200, body, {"content-encoding": "gzip"})), []
    resp = client(fake, sleeps, snapshot_dir=tmp_path).get("https://x.test")
    assert resp.json() == {"a": 1}
    (snap,) = tmp_path.iterdir()
    assert snap.name == f"{resp.sha256}.json.gz"
    assert gzip.decompress(snap.read_bytes()).endswith(b'{"a":1}')
