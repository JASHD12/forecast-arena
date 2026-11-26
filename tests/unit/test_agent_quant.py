"""T341-T343: the numeric tools, `agent_quant` and `agent_analyst`."""

import json
from datetime import UTC, datetime

import pytest
from factories import B, forecast, question

from arena.agent import quant
from arena.agent.forecaster import AgentForecaster
from arena.agent.tools import ToolBox, normal_probability
from arena.llm import prompts
from arena.llm.client import FakeLLM, ToolCall, ToolResults, tool_reply
from arena.models import Forecast

ASOF = datetime(2026, 11, 12, 6, tzinfo=UTC)
GOOD = json.dumps({"probability": 0.7, "rationale": "Estimate and evidence.", "key_factors": ["x"]})


def _daily(values: list[float], stat: str = "mean") -> dict:
    return {"daily": [{"day": f"2026-10-{i + 1:02d}", stat: v} for i, v in enumerate(values)]}


def _power_q(threshold: float = 80.0, template: str = "mean_gt"):
    q = question(template=template)
    return q.model_copy(update={"threshold": threshold, "params": {"stat": "mean"}})


def test_normal_probability_matches_known_values_and_rejects_bad_input() -> None:
    assert normal_probability(0, 1, 0, "gt") == pytest.approx(0.5)
    assert normal_probability(0, 1, 1.0, "gt") == pytest.approx(0.158655, abs=1e-5)
    assert normal_probability(0, 1, 1.0, "lt") == pytest.approx(0.841345, abs=1e-5)
    with pytest.raises(ValueError):
        normal_probability(0, 0, 1, "gt")
    with pytest.raises(ValueError):
        normal_probability(0, 1, 1, "up")


def test_toolbox_calculator_and_estimate_run_inside_the_call_limit() -> None:
    box = ToolBox({}, ASOF, max_calls=2, estimate=lambda: {"probability": 0.4})
    text, err = box.run(
        ToolCall(
            "1", "calculate_probability", {"center": 5, "sd": 2, "threshold": 7, "direction": "gt"}
        )
    )
    assert not err and json.loads(text)["data"]["probability"] == pytest.approx(0.1587, abs=1e-4)
    text, err = box.run(ToolCall("2", "estimate_probability", {}))
    assert not err and json.loads(text)["data"]["probability"] == 0.4
    _, err = box.run(ToolCall("3", "estimate_probability", {}))
    assert err  # the limit still applies
    none = ToolBox({}, ASOF)
    assert none.run(ToolCall("4", "estimate_probability", {}))[1]  # no reference model: an error
    assert none.run(
        ToolCall(
            "5", "calculate_probability", {"center": 1, "sd": -1, "threshold": 0, "direction": "gt"}
        )
    )[1]


def test_power_estimate_uses_only_the_stored_window_and_clips() -> None:
    q = _power_q(80.0)
    ctx = _daily([70, 75, 85, 90, 95, 100, 105, 110, 90, 95])  # all but three above 80
    out = quant.power_estimate(q, ctx)
    assert out["inputs"]["days_in_window"] == 10
    assert out["inputs"]["share_window"] == 0.8 and out["inputs"]["latest_day_crossed"] is True
    assert out["probability"] == pytest.approx((0.8 + 1.0 + 1.0) / 3, abs=1e-3)
    low = quant.power_estimate(q, _daily([10.0] * 10))
    assert low["probability"] == 0.05  # clipped, never 0
    with pytest.raises(ValueError):
        quant.power_estimate(q, _daily([90, 91, 92]))  # too little history


def test_power_estimate_respects_the_less_than_comparator() -> None:
    q = question(template="min_lt").model_copy(
        update={"threshold": 0.0, "comparator": "lt", "params": {"stat": "min"}}
    )
    out = quant.power_estimate(q, _daily([-5.0, 3.0, -1.0, 2.0, -2.0, 4.0, 5.0, 1.0], "min"))
    assert out["inputs"]["share_window"] == 0.375 and out["inputs"]["latest_day_crossed"] is False


def test_weather_estimate_is_the_ml_rule_and_other_topics_have_none() -> None:
    from arena.forecasters.ml_weather import WeatherRules

    q = question().model_copy(
        update={"domain": "weather", "template": "tmax_gt", "threshold": 7.0, "params": {}}
    )
    ctx = {"forecast_daily": {"tmax": 9.0, "precip": 0.0}}
    assert quant.numeric_estimate(q, ctx)["probability"] == pytest.approx(
        round(WeatherRules().probability(q, ctx), 3)
    )
    other = question().model_copy(update={"domain": "markets"})
    with pytest.raises(ValueError, match="no reference model"):
        quant.numeric_estimate(other, {})


class _Ml:
    forecaster_id = "ml"

    def version(self) -> str:
        return "ml-test"

    def forecast(self, q, ctx, asof):
        return forecast(q, "ml", 0.91)


def test_agent_quant_gets_its_own_prompt_tools_and_version() -> None:
    q = _power_q()
    ctx = _daily([90.0] * 10)
    fake = FakeLLM([tool_reply(ToolCall("c1", "estimate_probability", {})), GOOD])
    f = quant.AgentQuant(fake)
    out = f.forecast(q, ctx, ASOF)
    assert isinstance(out, Forecast) and out.forecaster_id == "agent_quant"
    assert "estimate_probability first" in fake.calls[0][0]  # the v3 system prompt
    assert out.forecaster_version.endswith(quant.QUANT_REVISION)
    sent = next(t for t in fake.calls[1][1] if isinstance(t, ToolResults)).results[0][1]
    assert json.loads(sent)["data"]["probability"] == 0.95
    assert out.forecaster_version != AgentForecaster(fake).version()
    names = {t.name for t in f.tools}
    assert {"estimate_probability", "calculate_probability", "get_ml_forecast"} <= names


def test_agent_analyst_starts_from_the_ml_forecast() -> None:
    q = question()
    fake = FakeLLM(
        [tool_reply(ToolCall("c1", "get_ml_forecast", {"question_id": q.question_id})), GOOD]
    )
    f = quant.AgentAnalyst(fake, peers={"ml": _Ml()})
    out = f.forecast(q, {}, ASOF)
    assert isinstance(out, Forecast) and out.forecaster_id == "agent_analyst"
    assert "Call get_ml_forecast first" in fake.calls[0][0]
    sent = next(t for t in fake.calls[1][1] if isinstance(t, ToolResults)).results[0][1]
    assert json.loads(sent)["data"]["probability"] == 0.91
    assert out.forecaster_version.endswith(quant.ANALYST_REVISION)
    assert "estimate_probability" not in {t.name for t in f.tools}


def test_the_existing_agents_keep_their_version_strings() -> None:
    """I8: per-file prompt versions must not change the fingerprint of the live agents."""
    f = AgentForecaster(FakeLLM([GOOD]))
    names = f.prompt_files
    assert prompts.fingerprint_map({n: "v1" for n in names}) == prompts.fingerprint(names, "v1")
    assert f.prompt_versions == {}


def test_wiring_registers_the_new_agents_only_when_switched_on(tmp_path) -> None:
    from arena.config import Settings
    from arena.ledger import Ledger
    from arena.ops.health import expected_forecasters
    from arena.ops.wiring import build_forecasters
    from arena.scoring.boards import COMMON_GROUP

    off, _ = build_forecasters(Ledger(tmp_path), [], Settings.from_env({}), B, llm=FakeLLM([GOOD]))
    assert not {"agent_quant", "agent_analyst"} & {f.forecaster_id for f in off}
    s = Settings.from_env({"ARENA_AGENT_QUANT": "1", "ARENA_AGENT_ANALYST": "1"})
    on, _ = build_forecasters(Ledger(tmp_path), [], s, B, llm=FakeLLM([GOOD]))
    ids = [f.forecaster_id for f in on]
    assert ids.index("agent_quant") == ids.index("agent") + 1
    assert ids.index("agent_analyst") == ids.index("agent") + 2
    assert {"agent_quant", "agent_analyst"} <= expected_forecasters(s)
    assert not {"agent_quant", "agent_analyst"} & set(COMMON_GROUP)
