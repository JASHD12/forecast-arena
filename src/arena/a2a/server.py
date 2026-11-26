"""A2A server side (T362): wrap an async handler as an `AgentExecutor` and build the ASGI app.

A handler takes the request payload (the JSON object the client sent) and returns a JSON-ready
result. The executor owns the protocol: it enqueues the `Task`, moves it through
`submitted -> working -> completed | failed`, publishes the result as one data artifact and turns
any exception or timeout into a `failed` task with the error text (never a silent drop).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from a2a.helpers.proto_helpers import new_data_part, new_task_from_user_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandlerV2
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import a2a_pb2 as pb
from starlette.applications import Starlette

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
ARTIFACT_NAME = "result"
DEFAULT_TIMEOUT = 120.0


def payload_of(message: pb.Message) -> dict[str, Any]:
    """The request payload: the first JSON text part, else a data part, else the plain text."""
    for part in message.parts:
        which = part.WhichOneof("content")
        if which == "text" and part.text.strip().startswith("{"):
            try:
                obj = json.loads(part.text)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
        if which == "data":
            from google.protobuf.json_format import MessageToDict

            obj = MessageToDict(part.data)
            if isinstance(obj, dict):
                return obj
    texts = [p.text for p in message.parts if p.WhichOneof("content") == "text"]
    return {"text": "\n".join(texts)}


class HandlerExecutor(AgentExecutor):
    """Runs `handler(payload)` as one A2A task."""

    def __init__(self, handler: Handler, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.handler = handler
        self.timeout = timeout

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """See `AgentExecutor.execute`."""
        assert context.message is not None and context.task_id and context.context_id
        task = context.current_task or new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.start_work()
        try:
            result = await asyncio.wait_for(
                self.handler(payload_of(context.message)), timeout=self.timeout
            )
        except TimeoutError:
            await updater.failed(
                updater.new_agent_message([new_text_part(f"timeout after {self.timeout:.0f}s")])
            )
            return
        except Exception as exc:  # the protocol reports it; the caller decides what it means
            await updater.failed(
                updater.new_agent_message([new_text_part(f"{type(exc).__name__}: {exc}"[:300])])
            )
            return
        await updater.add_artifact([new_data_part(result)], name=ARTIFACT_NAME)
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """See `AgentExecutor.cancel`."""
        assert context.task_id and context.context_id
        await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()


def build_app(
    card: pb.AgentCard, handler: Handler, *, timeout: float = DEFAULT_TIMEOUT
) -> Starlette:
    """An ASGI app serving `card` at the well-known path and `handler` over JSON-RPC at `/`."""
    request_handler = DefaultRequestHandlerV2(
        HandlerExecutor(handler, timeout=timeout), InMemoryTaskStore(), card
    )
    return Starlette(
        routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(request_handler, "/")]
    )
