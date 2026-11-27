"""Tool calls per answer on the LLM page (T380): counted over written forecasts only."""

from __future__ import annotations

from arena.site.llm_obs import tool_use_rows


def _t(fid: str, qid: str, outcome: str, tools: list[str] | None = None) -> dict:
    line: dict = {"forecaster_id": fid, "question_id": qid, "outcome": outcome}
    if tools is not None:
        line["tool_calls"] = [{"tool": x, "ok": True} for x in tools]
    return line


def test_counts_answers_calls_and_answers_without_tools() -> None:
    rows = tool_use_rows(
        [
            _t("agent", "weather-a-1", "forecast", []),
            _t("agent", "weather-a-2", "forecast", ["get_base_rate", "get_base_rate"]),
            _t("agent", "power-a-1", "forecast", ["similar_past_questions"]),
            _t("agent", "power-a-2", "parse_failure", ["get_base_rate"]),  # no answer: not counted
            _t("llm_context", "weather-a-1", "forecast"),  # no tools at all: the control
        ]
    )
    by = {(r.forecaster_id, r.topic): r for r in rows}
    w = by[("agent", "weather")]
    assert (w.answers, w.without_tools, w.tool_calls) == (2, 1, 2)
    assert w.by_tool == (("get_base_rate", 2),) and w.mean_calls == 1.0
    p = by[("agent", "power")]
    assert (p.answers, p.tool_calls) == (1, 1)
    c = by[("llm_context", "weather")]
    assert (c.answers, c.without_tools, c.tool_calls, c.mean_calls) == (1, 1, 0, 0.0)


def test_no_traces_gives_no_rows_and_rows_are_sorted() -> None:
    assert tool_use_rows([]) == []
    rows = tool_use_rows([_t("b", "x-1", "forecast"), _t("a", "y-1", "forecast")])
    assert [r.forecaster_id for r in rows] == ["a", "b"]
