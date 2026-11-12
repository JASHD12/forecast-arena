import json
from datetime import UTC, date, datetime, time

import pytest
from factories import question
from power_fixtures import fixture_domain

from arena.forecasters.llm import LLMContext, LLMPlain, daily_sample, render_context
from arena.llm.budget import BudgetGuard, Caps, GuardedLLM
from arena.llm.client import FakeLLM, LLMError, LLMRefusal, Usage, UserText
from arena.llm.parse import ParseError, parse_answer
from arena.models import Forecast, Skip

GOOD = json.dumps(
    {"probability": 0.42, "rationale": "Prices were falling.", "key_factors": ["wind", "weekend"]}
)
ASOF = datetime(2026, 11, 12, 6, tzinfo=UTC)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "0.4",
        "Probability: 0.4",
        "```json\n" + GOOD + "\n```",
        GOOD + " thanks",
        '{"probability": 1.2, "rationale": "x", "key_factors": []}',
        '{"probability": true, "rationale": "x", "key_factors": []}',
        '{"probability": NaN, "rationale": "x", "key_factors": []}',
        '{"probability": 0.4, "rationale": "x"}',
        '{"probability": 0.4, "rationale": "x", "key_factors": [], "extra": 1}',
        '{"probability": "0.4", "rationale": "x", "key_factors": []}',
        '{"probability": 0.4, "rationale": "' + "word " * 81 + '", "key_factors": []}',
        '{"probability": 0.4, "rationale": "x", "key_factors": "wind"}',
    ],
)
def test_malformed_answers_rejected(text: str) -> None:
    with pytest.raises(ParseError):
        parse_answer(text)


def test_good_answer() -> None:
    a = parse_answer("  " + GOOD + "\n")
    assert a.probability == 0.42 and a.key_factors == ("wind", "weekend")


def test_two_bad_answers_are_a_parse_failure_skip_never_a_number() -> None:
    fake = FakeLLM(["I think 40%", "still 40%"])
    out = LLMPlain(fake).forecast(question(), {}, ASOF)
    assert isinstance(out, Skip) and out.reason_code == "parse_failure"
    assert len(fake.calls) == 2  # exactly one repair retry


def test_repair_retry_can_succeed() -> None:
    fake = FakeLLM(["40%", GOOD])
    out = LLMPlain(fake).forecast(question(), {}, ASOF)
    assert isinstance(out, Forecast) and out.probability == 0.42
    assert out.rationale == "Prices were falling." and out.meta["usage"]["requests"] == 2
    assert "could not be parsed" in fake.calls[1][1][-1].text


def test_errors_refusals_missing_model() -> None:
    assert LLMPlain(None).forecast(question(), {}, ASOF).reason_code == "model_missing"
    assert (
        LLMPlain(FakeLLM([LLMError("500")])).forecast(question(), {}, ASOF).reason_code == "error"
    )
    assert (
        LLMPlain(FakeLLM([LLMRefusal("no")])).forecast(question(), {}, ASOF).reason_code == "error"
    )


def test_budget_cap_produces_budget_exhausted_skips() -> None:
    guard = BudgetGuard(Caps(2, 100_000, 400, 4), Usage())
    llm = GuardedLLM(FakeLLM([GOOD] * 5), guard)
    f = LLMPlain(llm)
    qs = [question(entity=e) for e in ("A1", "B1", "C1")]
    outs = [f.forecast(q, {}, ASOF) for q in qs]
    assert [type(o).__name__ for o in outs] == ["Forecast", "Forecast", "Skip"]
    assert outs[2].reason_code == "budget_exhausted"  # type: ignore[union-attr]


def test_plain_sees_no_data_context_does() -> None:
    fake_p, fake_c = FakeLLM([GOOD]), FakeLLM([GOOD])
    ctx = {"daily": [{"day": "2026-11-11", "mean": 123.45}]}
    LLMPlain(fake_p).forecast(question(), ctx, ASOF)
    LLMContext(fake_c).forecast(question(), ctx, ASOF)
    plain_msg, ctx_msg = fake_p.calls[0][1][0].text, fake_c.calls[0][1][0].text
    assert "123.45" not in plain_msg and "123.45" in ctx_msg
    assert "2026-11-12" in plain_msg and question().text in plain_msg
    assert '"probability"' in fake_p.calls[0][0]  # output contract in the system prompt


def test_sample_is_seeded_stratified_and_shared() -> None:
    dom = fixture_domain()
    b = date(2026, 10, 20)
    qs = dom.generate_questions(b, datetime.combine(b, time(5, 30), tzinfo=UTC))
    s = daily_sample(qs, 3)
    assert len(s) == 3 and s == daily_sample(list(reversed(qs)), 3)
    assert len({q.template for q in qs if q.question_id in s}) == 3
    plain, ctx = LLMPlain(FakeLLM([GOOD] * 9)), LLMContext(FakeLLM([GOOD] * 9))
    for f in (plain, ctx):
        f.prepare(qs)
    answered = {
        f.forecaster_id: {
            q.question_id for q in qs if isinstance(f.forecast(q, {}, ASOF), Forecast)
        }
        for f in (plain, ctx)
    }
    assert answered["llm_plain"] == answered["llm_context"] == s


def test_render_context_truncates() -> None:
    assert render_context({"x": "y" * 10_000}, limit=100).endswith("...(truncated)")
    assert isinstance(UserText("a").text, str)
