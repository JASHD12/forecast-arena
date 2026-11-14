"""T191: OTLP/JSON export of the LLM call spans follows the OTLP JSON encoding rules."""

import json
import re

from arena.llm.otlp import SPAN_KIND_CLIENT, otlp_names, otlp_span, traces_data, write_otlp

SPAN = {
    "name": "llm.complete", "forecaster_id": "agent", "question_id": "power-x-2026-11-14-v1",
    "prompt_version": "v2", "seq": 1, "start": "2026-11-13T05:30:01.250000+00:00",
    "duration_ms": 1500.5, "provider": "anthropic", "model": "claude-haiku-5-5",
    "input_tokens": 100, "output_tokens": 40, "cache_read_tokens": 600,
    "cache_write_tokens": 0, "tools_requested": ["get_series"], "stop_reason": "tool_use",
    "repair": False, "error": None, "day": "2026-11-13",
}  # fmt: skip


def test_span_follows_the_otlp_json_rules() -> None:
    o = otlp_span(SPAN)
    assert re.fullmatch(r"[0-9a-f]{32}", o["traceId"]) and re.fullmatch(
        r"[0-9a-f]{16}", o["spanId"]
    )
    assert o["kind"] == SPAN_KIND_CLIENT == 3 and isinstance(o["kind"], int)
    assert isinstance(o["startTimeUnixNano"], str) and isinstance(o["endTimeUnixNano"], str)
    assert int(o["endTimeUnixNano"]) - int(o["startTimeUnixNano"]) == 1_500_500_000
    assert o["name"] == "chat claude-haiku-5-5"
    attrs = {a["key"]: a["value"] for a in o["attributes"]}
    assert attrs["gen_ai.usage.input_tokens"] == {"intValue": "700"}  # 100 + 600 cached
    assert attrs["gen_ai.usage.cache_read.input_tokens"] == {"intValue": "600"}
    assert "gen_ai.usage.cache_write.input_tokens" not in attrs  # zero is omitted
    assert attrs["gen_ai.request.model"] == {"stringValue": "claude-haiku-5-5"}
    assert attrs["arena.repair"] == {"boolValue": False}
    assert attrs["gen_ai.response.finish_reasons"]["arrayValue"]["values"] == [
        {"stringValue": "tool_use"}
    ]
    assert "status" not in o
    assert "trace_id" not in json.dumps(o)  # lowerCamelCase keys only


def test_error_status_and_determinism(tmp_path) -> None:
    bad = {**SPAN, "error": "LLMError: anthropic HTTP 400", "stop_reason": ""}
    o = otlp_span(bad)
    assert o["status"]["code"] == 2 and "HTTP 400" in o["status"]["message"]
    assert {a["key"]: a["value"] for a in o["attributes"]}["error.type"] == {
        "stringValue": "LLMError"
    }
    assert otlp_span(SPAN) == otlp_span(dict(SPAN))
    assert otlp_span(SPAN)["spanId"] != otlp_span({**SPAN, "seq": 2})["spanId"]
    doc = traces_data([SPAN, bad])
    scope = doc["resourceSpans"][0]["scopeSpans"][0]
    assert len(scope["spans"]) == 2 and scope["scope"]["name"] == "arena.llm.tracing"
    assert doc["resourceSpans"][0]["resource"]["attributes"][0]["key"] == "service.name"


def test_write_one_file_per_day(tmp_path) -> None:
    other = {**SPAN, "day": "2026-11-12", "start": "2026-11-12T05:30:00+00:00"}
    assert write_otlp([], tmp_path / "o") == [] and not (tmp_path / "o").exists()
    names = write_otlp([SPAN, other], tmp_path / "o")
    assert (
        names == otlp_names([SPAN, other]) == ["traces-2026-11-13.json", "traces-2026-11-12.json"]
    )
    doc = json.loads((tmp_path / "o" / names[0]).read_text())
    assert len(doc["resourceSpans"][0]["scopeSpans"][0]["spans"]) == 1
    first = (tmp_path / "o" / names[0]).read_bytes()
    write_otlp([SPAN, other], tmp_path / "o")
    assert (tmp_path / "o" / names[0]).read_bytes() == first


def test_site_publishes_otlp_files_and_links_them(tmp_path) -> None:
    import sys
    from datetime import UTC, datetime
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(root / "tests" / "e2e"), str(root / "tests" / "unit")]
    from test_e2e import run_schedule

    from arena.clock import FixedClock
    from arena.site.build import build_site

    led = run_schedule(tmp_path / "l")
    res = build_site(led, tmp_path / "site", FixedClock(datetime(2026, 10, 27, tzinfo=UTC)))
    files = sorted((res.out_dir / "data" / "otlp").glob("traces-*.json"))
    assert files
    page = (res.out_dir / "llm.html").read_text()
    assert "Trace export (OpenTelemetry)" in page and f'href="data/otlp/{files[-1].name}"' in page
    doc = json.loads(files[0].read_text())
    spans = doc["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert spans and all(len(s["traceId"]) == 32 for s in spans)
