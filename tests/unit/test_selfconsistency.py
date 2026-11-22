"""T298: self-consistency averages k answers, records their spread and skips with a reason."""

import json
from datetime import UTC, datetime

import pytest
from factories import question

from arena.forecasters import selfconsistency as sc
from arena.llm.client import FakeLLM, LLMError
from arena.models import Forecast, Skip

ASOF = datetime(2026, 11, 24, 7, tzinfo=UTC)


def answer(p: float) -> str:
    return json.dumps({"probability": p, "rationale": "r", "key_factors": []})


def run(replies):
    f = sc.SelfConsistency(FakeLLM(list(replies)))
    return f, f.forecast(question(), {}, ASOF)


def test_the_mean_of_five_answers_and_their_spread_are_recorded() -> None:
    f, out = run(answer(p) for p in (0.6, 0.7, 0.8, 0.7, 0.7))
    assert isinstance(out, Forecast) and out.probability == pytest.approx(0.7)
    info = out.meta["self_consistency"]
    assert info["k"] == 5 and info["answers"] == [0.6, 0.7, 0.8, 0.7, 0.7] and info["spread_sd"] > 0
    assert out.forecaster_id == "llm_context_sc5" and "selfcons-k5-mean" in out.forecaster_version
    assert len(f.client.calls) == 5  # type: ignore[union-attr]


def test_three_usable_answers_are_enough_fewer_are_a_skip() -> None:
    _, ok = run([answer(0.4), "garbage", "garbage", answer(0.5), answer(0.6)] + ["garbage"] * 6)
    assert isinstance(ok, Forecast) and ok.probability == pytest.approx(0.5)
    _, bad = run(["garbage"] * 12)
    assert (
        isinstance(bad, Skip)
        and bad.reason_code == "parse_failure"
        and "of 5 answers" in bad.detail
    )


def test_a_provider_error_is_an_error_skip() -> None:
    _, out = run([LLMError("boom")] * 5)
    assert isinstance(out, Skip) and out.reason_code == "error"


def test_it_is_an_evaluation_variant_not_a_live_forecaster() -> None:
    from arena.config import Settings
    from arena.evals.run import VARIANTS
    from arena.ops.health import expected_forecasters

    assert VARIANTS["llm_context_sc5"] is sc.SelfConsistency
    assert "llm_context_sc5" not in expected_forecasters(Settings.from_env({}))
