"""Prometheus metrics for the REST API (T295).

Request count and latency per route *template* (so a question id never becomes a label value:
bounded cardinality), the size of the served record, and calls of the ONNX prediction endpoint with
the model version in a label. Each app instance has its own registry, so tests can build many apps.
The `/metrics` endpoint is the text exposition format a Prometheus server scrapes.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST

BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)


class ApiMetrics:
    """The metric objects of one API instance."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "arena_http_requests_total",
            "HTTP requests by method, route template and status",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self.latency = Histogram(
            "arena_http_request_seconds",
            "HTTP request latency by route template",
            ["route"],
            buckets=BUCKETS,
            registry=self.registry,
        )
        self.questions = Gauge(
            "arena_ledger_questions", "Questions in the served snapshot", registry=self.registry
        )
        self.forecasts = Gauge(
            "arena_ledger_forecasts", "Forecasts in the served snapshot", registry=self.registry
        )
        self.predictions = Counter(
            "arena_predict_power_total",
            "Calls of POST /predict/power by outcome and model version",
            ["outcome", "version"],
            registry=self.registry,
        )

    def render(self) -> bytes:
        """The exposition text."""
        return generate_latest(self.registry)


def install(app: FastAPI, metrics: ApiMetrics) -> None:
    """Add the timing middleware and the `/metrics` route."""

    @app.middleware("http")
    async def _timing(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route: Any = request.scope.get("route")
            template = getattr(route, "path", None) or "unmatched"
            metrics.requests.labels(request.method, template, str(status)).inc()
            metrics.latency.labels(template).observe(time.perf_counter() - start)

    @app.get("/metrics", include_in_schema=False)
    def _metrics() -> Response:
        return Response(metrics.render(), media_type=CONTENT_TYPE_LATEST)
