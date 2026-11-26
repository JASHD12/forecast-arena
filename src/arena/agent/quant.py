"""`agent_quant` and `agent_analyst`: the tool-using agent with numbers to work from (T342, T343).

Both are experimental, new forecaster ids (integrity rule I8: the existing agents' records do not
change). They share the loop, limits, sampling, output contract and traces of `agent`; only the
prompt and the tools differ, and both differences are visible in the version string.

- `agent_quant` also gets `estimate_probability` (a reference estimate computed from the stored
  as-of context and the question only, no peers, no outcomes) and `calculate_probability`
  (normal-distribution arithmetic). Its prompt asks for a numeric estimate first and an
  adjustment for evidence second, and tells the model that hedging is punished by the score.
- `agent_skills` (T353) is `agent_quant` plus `load_skill` (see `agent/skills/`).
- `agent_graph_skills` and `agent_hybrid_skills` (T357, T358) add the same toolset to the
  LangGraph agent and to the hybrid-retrieval agent.
- `agent_analyst` keeps the existing tools; its prompt tells the model to start from the `ml`
  forecast (`get_ml_forecast`, which the live agent has had since the first version and never
  called) and to change it only for evidence the model cannot see, naming that evidence.

The reference estimate for weather is the `ml` weather rule itself (a fixed normal error around
the stored DWD forecast), so on weather a numerate agent can at best match `ml`; that is stated in
the pre-registration (`lab/prereg/llm-quant-tools.md`). For electricity it is a simple, documented
blend of how often recent days crossed the threshold. Other topics have no reference model and
the tool says so (a visible tool error, never a made-up number).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from arena.agent import skills
from arena.agent.forecaster import AgentForecaster
from arena.agent.graph import GraphAgentForecaster
from arena.agent.hybrid import AgentHybrid
from arena.agent.tools import (
    CALC_SPEC,
    ESTIMATE_SPEC,
    SIMILAR_SPEC,
    TOOL_SPECS,
    ToolBox,
    skill_spec,
)
from arena.forecasters.ml_weather import GUST_SIGMA, TMAX_SIGMA, TMIN_SIGMA, WeatherRules
from arena.models import Question

QUANT_REVISION = "quant-r1"
ANALYST_REVISION = "analyst-r1"
MIN_HISTORY_DAYS = 7
ESTIMATE_CLIP = (0.05, 0.95)
RECENT_DAYS = 7


def _hit(value: float, comparator: str, threshold: float) -> bool:
    """The question's comparison, as the resolver applies it."""
    if comparator == "gt":
        return value > threshold
    if comparator == "ge":
        return value >= threshold
    return value < threshold


def power_estimate(q: Question, ctx: Mapping[str, Any]) -> dict[str, Any]:
    """How often recent days crossed the question's threshold, blended with the latest day.

    estimate = mean of (share over the stored window, share over the last 7 days, 1 if the
    latest day crossed else 0), clipped to [0.05, 0.95]. Simple on purpose: a reference point
    for the model to adjust, not a competitor to the gradient-boosted `ml` model.
    """
    stat = str(q.params.get("stat", ""))
    threshold = float(q.params["reference_mean"]) if q.template == "up_vs_today" else q.threshold
    daily = [d for d in ctx.get("daily", []) if stat in d]
    if threshold is None or len(daily) < MIN_HISTORY_DAYS:
        raise ValueError("not enough stored history for a reference estimate")
    values = [float(d[stat]) for d in daily]
    hits = [_hit(v, q.comparator, float(threshold)) for v in values]
    share_all = sum(hits) / len(hits)
    recent = hits[-RECENT_DAYS:]
    share_recent = sum(recent) / len(recent)
    last = 1.0 if hits[-1] else 0.0
    p = min(ESTIMATE_CLIP[1], max(ESTIMATE_CLIP[0], (share_all + share_recent + last) / 3))
    return {
        "probability": round(p, 3),
        "method": (
            "mean of: share of stored days that crossed the threshold, share of the last 7 "
            "days, and whether the latest day crossed it; clipped to 0.05-0.95"
        ),
        "inputs": {
            "statistic": stat,
            "comparator": q.comparator,
            "threshold": float(threshold),
            "days_in_window": len(values),
            "share_window": round(share_all, 3),
            "share_last_7_days": round(share_recent, 3),
            "latest_day_value": values[-1],
            "latest_day_crossed": bool(hits[-1]),
        },
    }


def weather_estimate(q: Question, ctx: Mapping[str, Any]) -> dict[str, Any]:
    """The `ml` weather rule (normal error around the stored DWD forecast); see `ml_weather.py`."""
    p = WeatherRules().probability(q, dict(ctx))
    return {
        "probability": round(p, 3),
        "method": (
            "the stored DWD forecast as the centre of a normal error "
            f"(sd {TMAX_SIGMA} C maximum, {TMIN_SIGMA} C minimum, {GUST_SIGMA} km/h gusts); "
            "rain questions use steps of the forecast precipitation total"
        ),
        "inputs": {"template": q.template, "threshold": q.threshold},
    }


def numeric_estimate(q: Question, ctx: Mapping[str, Any]) -> dict[str, Any]:
    """Reference estimate for `q` from its stored context only; ValueError if none exists."""
    if q.domain == "power":
        return power_estimate(q, ctx)
    if q.domain == "weather":
        return weather_estimate(q, ctx)
    raise ValueError(f"no reference model for the {q.domain} topic; use calculate_probability")


class AgentQuant(AgentForecaster):
    """`agent_quant`: the agent plus a reference estimate and a probability calculator."""

    forecaster_id = "agent_quant"
    prompt_versions = {"agent_system": "v3"}  # noqa: RUF012 - read-only class default

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        extra = (ESTIMATE_SPEC, CALC_SPEC)
        self.tools = (*TOOL_SPECS, *extra, *((SIMILAR_SPEC,) if self.retriever is not None else ()))

    def version(self) -> str:
        """The agent version plus the revision of the quant tools."""
        return f"{super().version()}|{QUANT_REVISION}"

    def _toolbox(self, q: Question, ctx: dict[str, Any], asof: datetime, **extra: Any) -> ToolBox:
        return super()._toolbox(q, ctx, asof, estimate=lambda: numeric_estimate(q, ctx), **extra)


class AgentAnalyst(AgentForecaster):
    """`agent_analyst`: starts from the `ml` forecast and changes it only for evidence."""

    forecaster_id = "agent_analyst"
    prompt_versions = {"agent_system": "v4"}  # noqa: RUF012 - read-only class default

    def version(self) -> str:
        """The agent version plus the revision of the analyst prompt."""
        return f"{super().version()}|{ANALYST_REVISION}"


SKILLS_REVISION = "skills-r1"


class AgentSkills(AgentQuant):
    """`agent_skills` (T353): `agent_quant` plus `load_skill`, progressive disclosure of skills.

    The prompt (`agent_system_v5`) carries a one-line index of the skills; the model may load the
    text of at most two per question, which does not use up its research calls, so the research
    budget equals `agent_quant`'s. The version string carries a fingerprint of every skill file,
    so any edit to a skill is a visible version change (I8).
    """

    forecaster_id = "agent_skills"
    prompt_versions = {"agent_system": "v5"}  # noqa: RUF012 - read-only class default

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.tools = (*self.tools, skill_spec())

    def version(self) -> str:
        """The quant version plus the skills revision and the fingerprint of every skill file."""
        return f"{super().version()}|{SKILLS_REVISION}-{skills.fingerprint()}"

    def _system(self) -> str:
        return super()._system().replace("{skills_index}", skills.index_text())

    def _toolbox(self, q: Question, ctx: dict[str, Any], asof: datetime, **extra: Any) -> ToolBox:
        return super()._toolbox(q, ctx, asof, skills=skills.load, **extra)


class _QuantSkillsTools:
    """What the graph and hybrid skills variants add to their base agent (T357, T358).

    The same toolset as `agent_skills`: `estimate_probability`, `calculate_probability` and
    `load_skill`. Skill loads keep their own limit and bypass any tool-output guard (the text is
    trusted operator text); estimate and calculator results pass through the guard like any
    other tool result.
    """

    tools: tuple[Any, ...]

    def _add_quant_skill_tools(self) -> None:
        self.tools = (*self.tools, ESTIMATE_SPEC, CALC_SPEC, skill_spec())

    @staticmethod
    def _quant_skills_extra(q: Question, ctx: dict[str, Any]) -> dict[str, Any]:
        return {"estimate": lambda: numeric_estimate(q, ctx), "skills": skills.load}

    @staticmethod
    def _version_suffix() -> str:
        return f"|{QUANT_REVISION}|{SKILLS_REVISION}-{skills.fingerprint()}"


class AgentGraphSkills(_QuantSkillsTools, GraphAgentForecaster):
    """`agent_graph_skills`: `agent_graph` plus the estimate, the calculator and `load_skill`.

    The graph's system and critique prompts are version 2 (they carry the skills index, the
    estimate-first rule and a consistency check against the estimate); the plan, evidence, user,
    final and repair prompts stay as `agent_graph`'s.
    """

    forecaster_id = "agent_graph_skills"
    prompt_versions = {"graph_system": "v2", "graph_critique": "v2"}  # noqa: RUF012

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._add_quant_skill_tools()

    def version(self) -> str:
        """The graph version plus the quant and skills revisions."""
        return f"{super().version()}{self._version_suffix()}"

    def _system(self) -> str:
        return super()._system().replace("{skills_index}", skills.index_text())

    def _toolbox(self, q: Question, ctx: dict[str, Any], asof: datetime, **extra: Any) -> ToolBox:
        return super()._toolbox(q, ctx, asof, **self._quant_skills_extra(q, ctx), **extra)


class AgentHybridSkills(_QuantSkillsTools, AgentHybrid):
    """`agent_hybrid_skills`: `agent_hybrid` plus the estimate, the calculator and `load_skill`.

    Uses prompt `agent_system_v5` (the skills prompt; it already says "if similar_past_questions
    is offered") with the hybrid agent's other prompts; a missing reranker or retriever is the same
    visible `model_missing` skip as for `agent_hybrid`.
    """

    forecaster_id = "agent_hybrid_skills"
    prompt_versions = {"agent_system": "v5"}  # noqa: RUF012 - read-only class default

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._add_quant_skill_tools()

    def version(self) -> str:
        """The hybrid version plus the quant and skills revisions."""
        return f"{super().version()}{self._version_suffix()}"

    def _system(self) -> str:
        return super()._system().replace("{skills_index}", skills.index_text())

    def _toolbox(self, q: Question, ctx: dict[str, Any], asof: datetime, **extra: Any) -> ToolBox:
        return super()._toolbox(q, ctx, asof, **self._quant_skills_extra(q, ctx), **extra)
