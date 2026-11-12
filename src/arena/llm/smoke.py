"""Live LLM smoke check (T064): two calls through the configured client, nothing written.

Call 1 sends the production system prompt with a fixed, non-live practice question and
checks that the reply passes the strict output contract (SPEC 9.2). Call 2 offers one
harmless tool and checks that the tool-use wire format round-trips (the model may or may
not call it; both are reported). Usage comes from the provider's own usage fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from arena.llm.client import LLMClient, LLMError, ToolSpec, Usage, UserText
from arena.llm.parse import ParseError, parse_answer
from arena.llm.prompts import load as load_prompt

PRACTICE_QUESTION = (
    "Practice question (not part of the benchmark): Will the sun rise in Berlin, "
    "Germany, on the next calendar day? Resolution: YES if sunrise occurs."
)
TOOL = ToolSpec(
    name="get_utc_date",
    description="Returns today's UTC date. Takes no arguments.",
    input_schema={"type": "object", "properties": {}},
)


@dataclass
class SmokeResult:
    """Outcome of the two calls."""

    lines: list[str] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    ok: bool = True


def run_smoke(client: LLMClient, max_tokens: int) -> SmokeResult:
    """Make exactly two calls; never raises for provider or parse failures."""
    res = SmokeResult()
    res.lines.append(f"provider={client.provider} model={client.model}")
    try:
        r1 = client.complete(
            load_prompt("system"), [UserText(PRACTICE_QUESTION)], max_tokens=max_tokens
        )
        res.usage = res.usage + r1.usage
        try:
            a = parse_answer(r1.text)
            res.lines.append(f"call 1: contract ok, probability={a.probability:.2f}")
        except ParseError as exc:
            res.ok = False
            res.lines.append(f"call 1: reply violates the output contract: {exc}")
        res.lines.append(
            f"call 1: served by {r1.model}, stop={r1.stop_reason}, {r1.usage.as_dict()}"
        )
    except LLMError as exc:
        res.ok = False
        res.lines.append(f"call 1 failed: {type(exc).__name__}: {exc}"[:300])
    try:
        r2 = client.complete(
            "You are testing a tool interface. Call the tool if it helps.",
            [UserText("What is today's UTC date? Use the tool.")],
            max_tokens=max_tokens,
            tools=[TOOL],
        )
        res.usage = res.usage + r2.usage
        names = [c.name for c in r2.tool_calls]
        res.lines.append(
            f"call 2: tool calls={names or 'none'}, stop={r2.stop_reason}, {r2.usage.as_dict()}"
        )
    except LLMError as exc:
        res.ok = False
        res.lines.append(f"call 2 failed: {type(exc).__name__}: {exc}"[:300])
    res.lines.append(f"total usage: {res.usage.as_dict()}")
    return res
