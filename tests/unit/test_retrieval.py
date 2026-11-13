"""The RAG tool (T120): retrieval of similar past questions, and its leakage rule."""

import json
from datetime import UTC, datetime, timedelta

from factories import B, question

from arena.agent.forecaster import AgentForecaster
from arena.agent.retrieval import HashEmbedder, PastQuestions
from arena.agent.tools import SIMILAR_SPEC
from arena.ledger import Ledger, layout
from arena.llm.client import FakeLLM, ToolCall, ToolResults, tool_reply
from arena.models import Evidence, Forecast, Resolution, Void

GOOD = json.dumps({"probability": 0.4, "rationale": "Similar days.", "key_factors": ["x"]})


def _res(q, outcome: int, at: datetime) -> Resolution:
    return Resolution(question_id=q.question_id, outcome=outcome, observed_value=81.0,
                      resolved_at=at, evidence=Evidence(source_url="https://x",
                      snapshot_sha256="a" * 64, values_used={}))  # fmt: skip


def _ledger(tmp_path) -> tuple[Ledger, list, datetime]:
    """Four days of questions: day 0-1 resolved early, day 2 resolved late, day 3 open,
    plus one voided question on day 0."""
    led = Ledger(tmp_path)
    days = [B + timedelta(days=i) for i in range(4)]
    qs = [question(batch=d) for d in days]
    bug = question(batch=days[0], template="max_gt")
    for d, q in zip(days, qs, strict=True):
        led.append(layout.questions_path(d), [q, bug] if d == days[0] else [q])
    asof = datetime.combine(days[3], datetime.min.time(), tzinfo=UTC) + timedelta(hours=6)
    led.append(layout.resolutions_path(days[0]), [_res(qs[0], 1, qs[0].resolve_after),
                                                  _res(bug, 1, bug.resolve_after)])  # fmt: skip
    led.append(layout.resolutions_path(days[1]), [_res(qs[1], 0, qs[1].resolve_after)])
    led.append(layout.resolutions_path(days[2]), [_res(qs[2], 1, asof + timedelta(minutes=1))])
    led.append(layout.resolutions_path(days[0]),
               [Void(question_id=bug.question_id, reason_code="bug", detail="test",
                     voided_at=bug.resolve_after)])  # fmt: skip
    return led, qs, asof


def test_leakage_only_questions_resolved_before_asof_are_returned(tmp_path) -> None:
    led, qs, asof = _ledger(tmp_path)
    idx = PastQuestions.from_ledger(led, HashEmbedder())
    ids = {p.question_id for p in idx.items}
    assert qs[3].question_id not in ids  # open questions are not even indexed
    assert len(ids) == 3  # the voided question is left out
    hits = idx.search(qs[3].text, asof, k=10, exclude=qs[3].question_id)
    assert [p.question_id for p, _ in hits] == sorted([qs[0].question_id, qs[1].question_id])
    # resolved one minute after the forecast time: never returned at asof, returned later
    later = idx.search(qs[3].text, asof + timedelta(minutes=2), k=10)
    assert qs[2].question_id in {p.question_id for p, _ in later}
    # a question never retrieves itself
    own = idx.search(qs[0].text, asof, exclude=qs[0].question_id)
    assert qs[0].question_id not in {p.question_id for p, _ in own}
    assert idx.search("x", datetime(2000, 1, 1, tzinfo=UTC)) == []


def test_similarity_order_and_tool_result(tmp_path) -> None:
    led, qs, asof = _ledger(tmp_path)
    idx = PastQuestions.from_ledger(led, HashEmbedder())
    res = idx.tool_result(qs[0].text, asof, k=2, exclude="none", domain="power")
    assert res["matches"][0]["question"] == qs[0].text  # identical text ranks first
    assert res["matches"][0]["similarity"] == 1.0
    assert res["yes_rate_of_matches"] == 0.5 and res["embedder"] == "hash-bow-256"
    assert idx.tool_result("x", asof, k=3, exclude="", domain="weather")["matches"] == []


def test_agent_offers_the_tool_only_with_a_retriever(tmp_path) -> None:
    led, qs, asof = _ledger(tmp_path)
    idx = PastQuestions.from_ledger(led, HashEmbedder())
    fake = FakeLLM([tool_reply(ToolCall("c1", "similar_past_questions", {"k": 3})), GOOD])
    a = AgentForecaster(fake, retriever=idx, prompt_version="v2")
    out = a.forecast(qs[3], {}, asof)
    assert isinstance(out, Forecast) and "prompt-v2" in out.forecaster_version
    assert "rag-hash-bow-256" in out.forecaster_version
    assert SIMILAR_SPEC.name in [t.name for t in fake.calls[0][2]]
    (res,) = [t for t in fake.calls[1][1] if isinstance(t, ToolResults)]
    data = json.loads(res.results[0][1])["data"]
    assert {m["target_date"] for m in data["matches"]} == {str(qs[0].target_date),
                                                           str(qs[1].target_date)}  # fmt: skip
    plain = FakeLLM([GOOD])
    AgentForecaster(plain).forecast(qs[3], {}, asof)
    assert SIMILAR_SPEC.name not in [t.name for t in plain.calls[0][2]]


def test_wiring_switches_the_agent_to_rag_and_prompt_v2(tmp_path, monkeypatch) -> None:
    from arena import config
    from arena.agent import retrieval
    from arena.ops.wiring import build_forecasters

    led, _, _ = _ledger(tmp_path)
    monkeypatch.setattr(retrieval, "FastEmbedder", lambda cache_dir=None: HashEmbedder())
    on = config.Settings.from_env({"ARENA_AGENT_RAG": "1"})
    fs, _ = build_forecasters(led, [], on, B, llm=FakeLLM([GOOD]))
    (agent,) = [f for f in fs if f.forecaster_id == "agent"]
    assert agent.retriever is not None and agent.prompt_version == "v2"  # type: ignore[attr-defined]
    off = config.Settings.from_env({})
    fs, _ = build_forecasters(led, [], off, B, llm=FakeLLM([GOOD]))
    (agent,) = [f for f in fs if f.forecaster_id == "agent"]
    assert agent.retriever is None and agent.prompt_version == "v1"  # type: ignore[attr-defined]
