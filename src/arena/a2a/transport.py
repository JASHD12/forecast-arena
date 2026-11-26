"""Transports (T362): in-process (ASGI, no socket) for the job and tests; localhost for `serve`.

The in-process hub builds one ASGI app per agent and gives each its own `httpx` client over
`httpx.ASGITransport`. Requests still travel the real JSON-RPC route, card included, so the card,
the task lifecycle and the serialisation behave exactly as over HTTP; only the socket is missing.
"""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Awaitable, Mapping
from concurrent.futures import ThreadPoolExecutor
from types import TracebackType
from typing import TypeVar

import httpx

from arena.a2a.cards import AgentSpec, build_card
from arena.a2a.client import A2AClient
from arena.a2a.server import Handler, build_app

T = TypeVar("T")


def base_url(name: str) -> str:
    """The in-process base URL of agent `name` (a reserved `.invalid` host, never resolved)."""
    return f"http://{name}.a2a.invalid"


class InProcessHub:
    """All agents of one run, reachable by name without opening a socket."""

    def __init__(
        self,
        agents: Mapping[str, tuple[AgentSpec, Handler]],
        *,
        server_timeout: float = 120.0,
        client_timeout: float = 130.0,
    ) -> None:
        self.agents = dict(agents)
        self.server_timeout = server_timeout
        self.client_timeout = client_timeout
        self._http: dict[str, httpx.AsyncClient] = {}
        self._clients: dict[str, A2AClient] = {}

    async def __aenter__(self) -> InProcessHub:
        for name, (spec, handler) in self.agents.items():
            app = build_app(
                build_card(spec, f"{base_url(name)}/"), handler, timeout=self.server_timeout
            )
            http = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url=base_url(name)
            )
            self._http[name] = http
            self._clients[name] = A2AClient(name, http, base_url(name), timeout=self.client_timeout)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        for http in self._http.values():
            await http.aclose()

    def client(self, name: str) -> A2AClient:
        """The client for agent `name` (KeyError for an unknown name)."""
        return self._clients[name]


def run_sync[T](coro: Awaitable[T]) -> T:
    """Run a coroutine to completion from synchronous code, also when a loop is already running.

    The caller's context variables (the tracing scope) carry over into the coroutine.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_wrap(coro))
    ctx = contextvars.copy_context()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(ctx.run, asyncio.run, _wrap(coro)).result()


async def _wrap[T](coro: Awaitable[T]) -> T:
    return await coro


def serve(spec: AgentSpec, handler: Handler, *, host: str, port: int) -> None:  # pragma: no cover
    """Serve one agent on localhost until interrupted (development use; needs `uvicorn`)."""
    import uvicorn

    app = build_app(build_card(spec, f"http://{host}:{port}/"), handler)
    uvicorn.run(app, host=host, port=port, log_level="warning")


__all__ = ["InProcessHub", "base_url", "run_sync", "serve"]
