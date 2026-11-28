"""T351-T354: the forecasting skills, the `load_skill` tool and `agent_skills`."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest
from factories import B, question

from arena.agent import quant, skills
from arena.agent.forecaster import AgentForecaster
from arena.agent.tools import MAX_SKILL_LOADS, SKILL_TOOL, ToolBox, skill_spec
from arena.llm.client import FakeLLM, ToolCall, ToolResults, tool_reply
from arena.models import Forecast

ASOF = datetime(2026, 11, 12, 6, tzinfo=UTC)
GOOD = json.dumps({"probability": 0.7, "rationale": "Estimate and evidence.", "key_factors": ["x"]})
SKILL_DIR = Path(skills.__file__).parent
TOPICS = {"all", "power", "weather", "attention", "markets", "crypto"}


def test_every_skill_has_complete_front_matter_and_a_bounded_body() -> None:
    assert skills.names() == sorted(
        [
            "crypto-moves",
            "electricity-day-ahead",
            "forecasting-core",
            "fx-ecb-moves",
            "weather-dwd-mosmix",
            "wikipedia-attention",
        ]
    )
    for name in skills.names():
        s = skills.get(name)
        assert s.name == name and s.description and s.revision >= 1
        assert set(s.topics) <= TOPICS and s.topics
        assert len(s.body.split()) <= skills.MAX_WORDS
        assert "\n" not in s.description


def test_every_topic_of_the_questions_has_a_skill() -> None:
    covered = {t for n in skills.names() for t in skills.get(n).topics}
    assert {"power", "weather", "attention", "markets", "crypto"} <= covered


def test_skills_contain_no_date_on_or_after_the_cutoff_and_keep_their_provenance() -> None:
    """I8: nothing from the live record; generated blocks name their source run and cut-off."""
    for f in SKILL_DIR.glob("*/SKILL.md"):
        text = f.read_text(encoding="utf-8")
        assert not [d for d in re.findall(r"\d{4}-\d{2}-\d{2}", text) if d > skills.CUTOFF], f.name
        blocks = re.findall(r"<!-- generated:(\w+) -->\n(.*?)<!-- /generated:\1 -->", text, re.S)
        for _, body in blocks:
            assert "scripts/skill_tables.py" in body and "backtest run" in body


def test_the_two_data_skills_carry_their_generated_tables() -> None:
    for name, block in (
        ("electricity-day-ahead", "power_rates"),
        ("fx-ecb-moves", "markets_rates"),
    ):
        text = (SKILL_DIR / name / "SKILL.md").read_text(encoding="utf-8")
        assert f"<!-- generated:{block} -->" in text and "| Template |" in text


def test_loader_index_fingerprint_and_unknown_names() -> None:
    assert skills.load("forecasting-core").startswith("# Skill: forecasting-core")
    idx = skills.index_text()
    assert all(f"- {n}:" in idx for n in skills.names())
    assert re.fullmatch(r"[0-9a-f]{8}", skills.fingerprint())
    with pytest.raises(KeyError, match="available"):
        skills.load("nope")
    assert skill_spec().input_schema["properties"]["name"]["enum"] == skills.names()


def test_skill_loads_have_their_own_limit_and_do_not_use_research_calls() -> None:
    box = ToolBox({}, ASOF, max_calls=1, skills=skills.load)
    for name in ("forecasting-core", "crypto-moves"):
        text, err = box.run(ToolCall(name, SKILL_TOOL, {"name": name}))
        assert not err and json.loads(text)["data"]["skill"].startswith("# Skill:")
    assert box.calls_left == 1  # both loads were free
    _, err = box.run(ToolCall("x", SKILL_TOOL, {"name": "fx-ecb-moves"}))
    assert err and MAX_SKILL_LOADS == 2  # the third is refused
    assert (
        box.run(
            ToolCall(
                "g",
                "calculate_probability",
                {"center": 0, "sd": 1, "threshold": 0, "direction": "gt"},
            )
        )[1]
        is False
    )
    assert box.calls_left == 0
    bad = ToolBox({}, ASOF, skills=skills.load)
    assert bad.run(ToolCall("u", SKILL_TOOL, {"name": "nope"}))[1]  # unknown skill: a tool error
    assert ToolBox({}, ASOF).run(ToolCall("n", SKILL_TOOL, {"name": "forecasting-core"}))[1]


def test_agent_skills_flow_and_version() -> None:
    q = question().model_copy(update={"threshold": 80.0, "params": {"stat": "mean"}})
    ctx = {"daily": [{"day": f"2026-10-{i + 1:02d}", "mean": 90.0} for i in range(10)]}
    fake = FakeLLM(
        [
            tool_reply(ToolCall("c1", SKILL_TOOL, {"name": "electricity-day-ahead"})),
            tool_reply(ToolCall("c2", "estimate_probability", {})),
            GOOD,
        ]
    )
    f = quant.AgentSkills(fake)
    out = f.forecast(q, ctx, ASOF)
    assert isinstance(out, Forecast) and out.forecaster_id == "agent_skills"
    assert "- electricity-day-ahead:" in fake.calls[0][0]  # the index is in the system prompt
    first_result = next(t for t in fake.calls[1][1] if isinstance(t, ToolResults)).results[0][1]
    assert "Skill: electricity-day-ahead" in first_result
    assert f"{quant.SKILLS_REVISION}-{skills.fingerprint()}" in out.forecaster_version
    assert f"|{quant.QUANT_REVISION}|{quant.SKILLS_REVISION}-" in out.forecaster_version
    assert out.forecaster_version != quant.AgentQuant(fake).version()
    (line,) = f.trace_lines()
    assert [t["tool"] for t in line["tool_calls"]] == [SKILL_TOOL, "estimate_probability"]
    assert line["tool_calls"][0]["args"] == {"name": "electricity-day-ahead"}
    assert "load_skill" in {t.name for t in f.tools}


def test_changing_a_skill_changes_the_version(monkeypatch) -> None:
    before = quant.AgentSkills(FakeLLM([GOOD])).version()
    monkeypatch.setattr(skills, "fingerprint", lambda: "deadbeef")
    after = quant.AgentSkills(FakeLLM([GOOD])).version()
    assert before != after and after.endswith("deadbeef")


def test_other_agents_do_not_offer_skills_and_keep_their_versions() -> None:
    names = lambda f: {t.name for t in f.tools}  # noqa: E731
    for f in (
        AgentForecaster(FakeLLM([GOOD])),
        quant.AgentQuant(FakeLLM([GOOD])),
        quant.AgentAnalyst(FakeLLM([GOOD])),
    ):
        assert SKILL_TOOL not in names(f)
    assert "{skills_index}" not in quant.AgentSkills(FakeLLM([GOOD]))._system()


def test_morning_workflow_runs_agent_skills_by_default_and_the_variable_can_switch_it_off() -> None:
    import re
    from pathlib import Path

    flow = (Path(__file__).parents[2] / ".github/workflows/morning.yml").read_text()
    line = next(ln for ln in flow.splitlines() if ln.strip().startswith("ARENA_AGENT_SKILLS:"))
    assert "vars.ARENA_AGENT_SKILLS || '1'" in line  # owner decision 2026-11-28 (DECISIONS)
    assert re.search(r"ARENA_LLM_MAX_TOKENS_PER_DAY \|\| '500000'", flow)


def test_wiring_registers_agent_skills_only_when_switched_on(tmp_path) -> None:
    from arena.config import Settings
    from arena.ledger import Ledger
    from arena.ops.health import expected_forecasters
    from arena.ops.wiring import build_forecasters
    from arena.scoring.boards import COMMON_GROUP

    off, _ = build_forecasters(Ledger(tmp_path), [], Settings.from_env({}), B, llm=FakeLLM([GOOD]))
    assert "agent_skills" not in [f.forecaster_id for f in off]
    s = Settings.from_env({"ARENA_AGENT_SKILLS": "1"})
    on, _ = build_forecasters(Ledger(tmp_path), [], s, B, llm=FakeLLM([GOOD]))
    ids = [f.forecaster_id for f in on]
    assert ids.index("agent_skills") == ids.index("agent") + 1
    assert "agent_skills" in expected_forecasters(s) and "agent_skills" not in COMMON_GROUP
