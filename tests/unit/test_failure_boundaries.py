"""The broad `except Exception` boundaries that remain turn a failure into a recorded skip,
warning or empty value, never into a substitute number (I6, T383)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

from crypto_fixtures import fixture_crypto

from arena.agent.forecaster import AgentForecaster
from arena.clock import FixedClock
from arena.models import Question, Skip
from arena.ops.jobs import _run_forecaster

ASOF = datetime(2026, 11, 10, 5, 30, tzinfo=UTC)


def _q() -> Question:
    b = date(2026, 11, 10)
    return fixture_crypto().generate_questions(b, datetime.combine(b, time(5, 30), tzinfo=UTC))[0]


class Boom:
    """A forecaster whose forecast and version both fail."""

    forecaster_id = "boom"

    def forecast(self, q: Question, ctx: dict[str, Any], asof: datetime) -> Any:
        raise RuntimeError("model exploded")

    def version(self) -> str:
        raise RuntimeError("no version either")


class Warnings:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def warn(self, msg: str) -> None:
        self.messages.append(msg)


def test_a_crashing_forecaster_becomes_an_error_skip_with_the_reason() -> None:
    rec = Warnings()
    out = _run_forecaster(Boom(), _q(), {}, FixedClock(ASOF), rec)  # type: ignore[arg-type]
    assert isinstance(out, Skip) and out.reason_code == "error"
    assert "model exploded" in out.detail and out.forecaster_version is None
    assert rec.messages and "boom failed on" in rec.messages[0]


def test_a_failing_peer_gives_the_tools_no_value_instead_of_a_guess() -> None:
    agent = AgentForecaster(None, peers={"ml": Boom()})  # type: ignore[dict-item]
    q = _q()
    assert agent._peer_probabilities(q, {}, ASOF) == {}
