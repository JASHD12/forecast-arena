"""Shared HTTP client: timeouts, retries with backoff, identifying User-Agent, snapshots.

Uses only the standard library. The network call is an injectable `Transport`, so tests
run with a fake transport and never touch the network.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class HttpRequest:
    """A GET request."""

    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    timeout: float = 30.0


@dataclass(frozen=True)
class HttpResponse:
    """A response body with its status and headers (header names lower-cased)."""

    url: str
    status: int
    headers: Mapping[str, str]
    body: bytes

    def json(self) -> object:
        """Decode the body as JSON."""
        return json.loads(self.body.decode("utf-8"))

    @property
    def sha256(self) -> str:
        """Hex SHA-256 of the body (used as evidence hash)."""
        return hashlib.sha256(self.body).hexdigest()


class HttpError(Exception):
    """Final failure after retries, or a non-retryable status."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


Transport = Callable[[HttpRequest], HttpResponse]


def urllib_transport(req: HttpRequest) -> HttpResponse:
    """The real network transport. Raises TimeoutError/OSError on network failures."""
    r = urllib.request.Request(req.url, headers=dict(req.headers), method="GET")
    try:
        with urllib.request.urlopen(r, timeout=req.timeout) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return HttpResponse(req.url, resp.status, headers, resp.read())
    except urllib.error.HTTPError as exc:
        headers = {k.lower(): v for k, v in (exc.headers or {}).items()}
        return HttpResponse(req.url, exc.code, headers, exc.read() or b"")
    except TimeoutError as exc:
        raise TimeoutError(str(exc)) from exc


class HttpClient:
    """GET with retries. One instance per job; carries the User-Agent from settings."""

    def __init__(
        self,
        user_agent: str,
        *,
        transport: Transport = urllib_transport,
        timeout: float = 30.0,
        retries: int = 3,
        backoff: float = 2.0,
        max_wait: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
        snapshot_dir: Path | None = None,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("a descriptive User-Agent is required")
        self.user_agent = user_agent
        self.transport = transport
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.max_wait = max_wait
        self.sleep = sleep
        self.snapshot_dir = snapshot_dir

    def get(self, url: str, params: Mapping[str, str] | None = None) -> HttpResponse:
        """GET `url` (with optional query params). Retries 429/5xx and network errors."""
        if params:
            url = f"{url}{'&' if '?' in url else '?'}{urllib.parse.urlencode(params)}"
        req = HttpRequest(
            url,
            {"User-Agent": self.user_agent, "Accept-Encoding": "gzip"},
            self.timeout,
        )
        last = "no attempt made"
        last_retry_after: str | None = None
        for attempt in range(self.retries + 1):
            if attempt:
                self.sleep(self._wait(attempt, last_retry_after))
                last_retry_after = None
            try:
                resp = self.transport(req)
            except (TimeoutError, OSError) as exc:
                last = f"{type(exc).__name__}: {exc}"
                continue
            if resp.status in RETRY_STATUS:
                last = f"HTTP {resp.status}"
                last_retry_after = resp.headers.get("retry-after")
                continue
            if resp.status >= 400:
                raise HttpError(f"GET {url} failed: HTTP {resp.status}", resp.status)
            resp = _decompress(resp)
            if self.snapshot_dir is not None:
                self._snapshot(resp)
            return resp
        raise HttpError(f"GET {url} failed after {self.retries + 1} attempts: {last}")

    def _wait(self, attempt: int, retry_after: str | None) -> float:
        if retry_after and retry_after.isdigit():
            return min(float(retry_after), self.max_wait)
        return min(self.backoff ** (attempt - 1), self.max_wait)

    def _snapshot(self, resp: HttpResponse) -> Path:
        assert self.snapshot_dir is not None
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.snapshot_dir / f"{resp.sha256}.json.gz"
        if not path.exists():
            meta = {"url": resp.url, "status": resp.status, "sha256": resp.sha256}
            payload = json.dumps(meta, sort_keys=True).encode() + b"\n" + resp.body
            path.write_bytes(gzip.compress(payload, mtime=0))
        return path


def _decompress(resp: HttpResponse) -> HttpResponse:
    if resp.headers.get("content-encoding", "").lower() == "gzip":
        return HttpResponse(resp.url, resp.status, resp.headers, gzip.decompress(resp.body))
    return resp
