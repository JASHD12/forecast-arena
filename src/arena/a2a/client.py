"""A2A client side (T362): ask one agent, get a `CallResult`, never an exception.

Retries are off on purpose (every call can cost model tokens and the budget is explicit); the caller
decides what a failed call means (the committee's quorum rule). Every call measures its duration and
message sizes, so a committee run produces one record per A2A call for the trace.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import get_message_text, new_message, new_text_part
from a2a.types import a2a_pb2 as pb
from google.protobuf.json_format import MessageToDict

COMPLETED = "COMPLETED"
FAILED = "FAILED"


@dataclass(frozen=True)
class CallResult:
    """The outcome of one A2A request."""

    agent: str
    state: (
        str  # task state without its prefix, e.g. COMPLETED, FAILED, or ERROR (transport/protocol)
    )
    data: dict[str, Any] | None
    error: str | None
    duration_ms: float
    bytes_out: int
    bytes_in: int
    task_id: str = ""

    @property
    def ok(self) -> bool:
        """True when the task completed and returned a data artifact."""
        return self.state == COMPLETED and self.data is not None

    def trace(self) -> dict[str, Any]:
        """A compact record for the trace (no payload text)."""
        return {
            "agent": self.agent,
            "state": self.state,
            "duration_ms": self.duration_ms,
            "bytes_out": self.bytes_out,
            "bytes_in": self.bytes_in,
            "error": self.error,
        }


class A2AClient:
    """A client for one agent reachable through `http` at `base_url`."""

    def __init__(
        self, name: str, http: httpx.AsyncClient, base_url: str, *, timeout: float = 120.0
    ) -> None:
        self.name = name
        self.http = http
        self.base_url = base_url
        self.timeout = timeout
        self._client: Any = None
        self._card: Any = None

    async def card(self) -> pb.AgentCard:
        """The agent's card, fetched through the SDK's resolver from the well-known path."""
        await self._ensure()
        return self._card

    async def _ensure(self) -> None:
        """Resolve the card once; every interface is pinned to the URL the card came from.

        A card is data from the other side: its `url` fields are not followed to another host, so a
        card cannot redirect this client (and a service behind a port mapping or a proxy works).
        """
        if self._client is None:
            card = await A2ACardResolver(self.http, self.base_url).get_agent_card()
            for iface in card.supported_interfaces:
                iface.url = self.base_url.rstrip("/") + "/"
            factory = ClientFactory(ClientConfig(httpx_client=self.http, streaming=False))
            self._client = factory.create(card)
            self._card = card

    async def ask(self, payload: dict[str, Any]) -> CallResult:
        """Send `payload` as one JSON message and wait for the task to finish."""
        started = time.monotonic()
        body = json.dumps(payload, ensure_ascii=False, default=str)
        out = len(body.encode())

        def done(
            state: str, data: Any, error: str | None, bytes_in: int, task_id: str = ""
        ) -> CallResult:
            ms = round((time.monotonic() - started) * 1000, 1)
            return CallResult(self.name, state, data, error, ms, out, bytes_in, task_id)

        try:
            return await asyncio.wait_for(self._ask(body, done), timeout=self.timeout)
        except TimeoutError:
            return done("ERROR", None, f"timeout after {self.timeout:.0f}s", 0)
        except Exception as exc:  # protocol, transport or serialisation failure
            return done("ERROR", None, f"{type(exc).__name__}: {exc}"[:300], 0)

    async def _ask(self, body: str, done: Any) -> CallResult:
        await self._ensure()
        message = new_message(
            [new_text_part(body, media_type="application/json")], role=pb.ROLE_USER
        )
        last: pb.Task | None = None
        async for resp in self._client.send_message(pb.SendMessageRequest(message=message)):
            if resp.WhichOneof("payload") == "task":
                last = resp.task
        if last is None:
            return done("ERROR", None, "no task in the response", 0)
        state = pb.TaskState.Name(last.status.state).removeprefix("TASK_STATE_")
        if state != COMPLETED:
            detail = (
                get_message_text(last.status.message) if last.status.HasField("message") else ""
            )
            return done(state, None, detail[:300] or state, 0, last.id)
        for art in last.artifacts:
            for part in art.parts:
                if part.WhichOneof("content") == "data":
                    data = MessageToDict(part.data)
                    return done(COMPLETED, data, None, len(json.dumps(data)), last.id)
        return done("ERROR", None, "completed task without a data artifact", 0, last.id)
