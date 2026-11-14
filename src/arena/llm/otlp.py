"""Export the LLM call spans as OpenTelemetry traces in OTLP/JSON (T191).

The spans are recorded by `llm/tracing.py` (one per model call) and stored in the ledger's
`agent_traces/`. This module writes them as an OTLP `TracesData` JSON document that any
OpenTelemetry collector or tracing backend can ingest, for example with
`curl -X POST -H 'Content-Type: application/json' --data @traces.json <collector>:4318/v1/traces`.

Encoding follows the OTLP specification (opentelemetry-proto `docs/specification.md`,
"JSON Protobuf Encoding", checked 2026-11-13): lowerCamelCase keys, `traceId` and
`spanId` as hex strings (16 and 8 bytes), enum values as integers, 64-bit integers
(timestamps, `intValue`) as decimal strings. Attribute names follow the OpenTelemetry
GenAI client-inference conventions (open-telemetry/semantic-conventions-genai, checked
2026-11-13): span name `{gen_ai.operation.name} {gen_ai.request.model}`, kind CLIENT,
`gen_ai.usage.input_tokens` including cached tokens.

Ids are derived deterministically from the span's content, so the export of a day is the
same every time it is built.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

SPAN_KIND_CLIENT = 3
STATUS_CODE_ERROR = 2
SCOPE = "arena.llm.tracing"


def _hex(*parts: object, nbytes: int) -> str:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[: 2 * nbytes]


def _nanos(iso: str) -> int:
    dt = datetime.fromisoformat(iso)
    return int(dt.timestamp()) * 1_000_000_000 + dt.microsecond * 1_000


def _value(v: object) -> dict[str, Any]:
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, list):
        return {"arrayValue": {"values": [_value(x) for x in v]}}
    return {"stringValue": str(v)}


def _attrs(d: dict[str, object]) -> list[dict[str, Any]]:
    return [{"key": k, "value": _value(v)} for k, v in d.items() if v is not None]


def otlp_span(s: dict[str, Any]) -> dict[str, Any]:
    """One stored span (`tracing.Span.as_dict()`) as an OTLP span."""
    trace_id = _hex(s.get("forecaster_id"), s.get("question_id"), s.get("day"), nbytes=16)
    start = _nanos(str(s["start"]))
    end = start + round(float(s.get("duration_ms", 0)) * 1_000_000)
    cache_read = int(s.get("cache_read_tokens", 0))
    cache_write = int(s.get("cache_write_tokens", 0))
    model = str(s.get("model", ""))
    attributes = {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": s.get("provider"),
        "gen_ai.request.model": model,
        # the convention counts cached tokens as input; Anthropic reports them apart
        "gen_ai.usage.input_tokens": int(s.get("input_tokens", 0)) + cache_read + cache_write,
        "gen_ai.usage.output_tokens": int(s.get("output_tokens", 0)),
        "gen_ai.usage.cache_read.input_tokens": cache_read or None,
        "gen_ai.usage.cache_write.input_tokens": cache_write or None,
        "gen_ai.response.finish_reasons": [s["stop_reason"]] if s.get("stop_reason") else None,
        "gen_ai.prompt.version": s.get("prompt_version") or None,
        "error.type": str(s["error"]).split(":", 1)[0] if s.get("error") else None,
        "arena.forecaster_id": s.get("forecaster_id"),
        "arena.question_id": s.get("question_id"),
        "arena.call_seq": int(s.get("seq", 0)),
        "arena.repair": bool(s.get("repair", False)),
        "arena.tools_requested": list(s.get("tools_requested") or []) or None,
    }
    out: dict[str, Any] = {
        "traceId": trace_id,
        "spanId": _hex(trace_id, s.get("seq"), s.get("start"), nbytes=8),
        "name": f"chat {model}".strip(),
        "kind": SPAN_KIND_CLIENT,
        "startTimeUnixNano": str(start),
        "endTimeUnixNano": str(end),
        "attributes": _attrs(attributes),
    }
    if s.get("error"):
        out["status"] = {"code": STATUS_CODE_ERROR, "message": str(s["error"])[:200]}
    return out


def traces_data(spans: list[dict[str, Any]], service: str = "forecast-arena") -> dict[str, Any]:
    """An OTLP `TracesData` document for the given stored spans."""
    ordered = sorted(spans, key=lambda s: (str(s.get("start")), int(s.get("seq", 0))))
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": _attrs({"service.name": service})},
                "scopeSpans": [
                    {"scope": {"name": SCOPE}, "spans": [otlp_span(s) for s in ordered]}
                ],
            }
        ]
    }


def _by_day(spans: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in spans:
        if s.get("day") is not None and s.get("start"):
            out[str(s["day"])].append(s)
    return out


def otlp_names(spans: list[dict[str, Any]]) -> list[str]:
    """The file names `write_otlp` will write, newest day first (for page links)."""
    return [f"traces-{d}.json" for d in sorted(_by_day(spans), reverse=True)]


def write_otlp(spans: list[dict[str, Any]], out_dir: Path) -> list[str]:
    """Write one `traces-YYYY-MM-DD.json` per batch day into `out_dir`.

    Returns the file names (newest day first); writes nothing when there are no spans.
    Each file is a complete OTLP `TracesData` document.
    """
    by_day = _by_day(spans)
    if not by_day:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    names = []
    for day in sorted(by_day, reverse=True):
        name = f"traces-{day}.json"
        text = json.dumps(traces_data(by_day[day]), indent=1, sort_keys=True)
        (out_dir / name).write_text(text + "\n", encoding="utf-8")
        names.append(name)
    return names
