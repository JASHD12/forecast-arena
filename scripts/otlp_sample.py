"""Print an OTLP/JSON `TracesData` document with a few model-call spans for a trace backend.

    python scripts/otlp_sample.py | curl -X POST -H 'content-type: application/json' \\
        --data-binary @- http://localhost:4318/v1/traces

The spans have the shape the project stores for real calls (`llm/tracing.py`) and are exported with
the OpenTelemetry GenAI attribute names (`llm/otlp.py`). Used by the CI job `observability` (Jaeger)
and `make smoke-observability`. The content is synthetic and says so in the forecaster id.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arena.llm.otlp import traces_data


def sample_spans(now: datetime | None = None) -> list[dict[str, object]]:
    """Three stored-style spans: a call, a repair of its answer, and an error."""
    t = (now or datetime.now(UTC)).isoformat()
    base = {
        "provider": "anthropic",
        "model": "claude-haiku-5-5",
        "forecaster_id": "sample_agent",
        "question_id": "sample-question",
        "day": "2026-11-22",
        "start": t,
        "prompt_version": "v-sample",
    }
    return [
        {
            **base,
            "seq": 1,
            "duration_ms": 850,
            "input_tokens": 1900,
            "output_tokens": 120,
            "stop_reason": "end_turn",
        },
        {
            **base,
            "seq": 2,
            "duration_ms": 420,
            "input_tokens": 2100,
            "output_tokens": 60,
            "stop_reason": "end_turn",
            "repair": True,
        },
        {
            **base,
            "seq": 3,
            "duration_ms": 90,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": "TimeoutError: sample failure",
        },
    ]


if __name__ == "__main__":
    json.dump(traces_data(sample_spans()), sys.stdout)
