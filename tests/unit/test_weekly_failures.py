"""Invalid or partial predictions cannot win the weekly model selection."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from click.testing import CliRunner
from factories import question, resolution

from arena.clock import FixedClock
from arena.forecasters import registry
from arena.ledger import Ledger
from arena.ops.weekly import evaluate, summaries, weekly

NOW = datetime(2026, 11, 12, 2, tzinfo=UTC)


class EvaluationDomain:
    name = "power"

    def generate_questions(self, batch, asof):
        return [question("A", batch), question("B", batch)]

    def context(self, q, asof):
        return {}

    def resolve(self, q, now):
        return resolution(q, 0)


@dataclass
class Model:
    version: str
    p: float = 0.4
    fail_on: str | None = None

    def probability(self, q, ctx):
        if q.entity == self.fail_on:
            raise ValueError("invalid feature schema")
        return self.p

    def model_hash(self):
        return self.version


def good(cut):
    return Model(f"test-{cut}")


@pytest.mark.parametrize("p", [float("nan"), float("inf"), -float("inf"), -0.1, 1.1])
def test_invalid_probabilities_are_disqualified_without_erasing_healthy_comparisons(p) -> None:
    errors, ids = {}, []
    day = date(2026, 11, 1)
    scores = evaluate(
        EvaluationDomain(),
        {"healthy": Model("good"), "invalid": Model("bad", p)},
        day,
        day,
        errors=errors,
        question_ids=ids,
    )
    assert scores == {"healthy": (pytest.approx(0.16), 2)}
    assert "invalid probability" in errors["invalid"]
    assert ids == [question("A", day).question_id, question("B", day).question_id]
    assert ids[0] in errors["invalid"]


def test_partial_candidate_is_disqualified_and_healthy_candidate_promoted(tmp_path) -> None:
    led = Ledger(tmp_path)
    res = weekly(
        led,
        FixedClock(NOW),
        {"power": EvaluationDomain()},
        {"power": {"healthy": good, "partial": lambda cut: Model("partial", 0.01, "B")}},
        drift=False,
    )
    d = res.decisions[0]
    assert res.ok and d.best_family == "healthy" and d.promoted
    assert len(d.evaluation_question_ids) == d.n == 56
    candidates = {c["family"]: c for c in d.candidates}
    assert candidates["partial"]["brier"] is None
    assert (
        candidates["partial"]["n"] == 0
        and "invalid feature schema" in candidates["partial"]["error"]
    )
    assert candidates["healthy"]["n"] == d.n


def test_all_invalid_preserves_champion_and_publishes_failed_outcome(tmp_path) -> None:
    led = Ledger(tmp_path)
    doms = {"power": EvaluationDomain()}
    first = weekly(led, FixedClock(NOW), doms, {"power": good}, drift=False)
    champion = first.decisions[0].promoted
    res = weekly(
        led,
        FixedClock(NOW + timedelta(days=7)),
        doms,
        {"power": lambda cut: Model("bad", float("nan"))},
        drift=False,
    )
    assert not res.ok and "prediction failed" in res.decisions[0].reason
    assert registry.current_version(led, "power") == champion
    assert res.decisions[0].promoted is None
    assert summaries(led)[0]["ok"] is False


def test_champion_failure_cannot_be_treated_as_first_model(tmp_path) -> None:
    led = Ledger(tmp_path)
    bad = Model("bad-current", fail_on="B")
    registry.save_model(led, "power", bad, created_at=NOW)
    registry.promote(led, "power", bad.version, at=NOW, reason="test")
    res = weekly(led, FixedClock(NOW), {"power": EvaluationDomain()}, {"power": good}, drift=False)
    assert not res.ok and "current model prediction failed" in res.decisions[0].reason
    assert registry.current_version(led, "power") == bad.version


def test_invalid_final_refit_is_not_published(tmp_path) -> None:
    def trainer(cut):
        return Model(f"test-{cut}", float("nan") if cut == NOW.date() - timedelta(days=3) else 0.4)

    led = Ledger(tmp_path)
    res = weekly(
        led, FixedClock(NOW), {"power": EvaluationDomain()}, {"power": trainer}, drift=False
    )
    assert not res.ok and "refit failed validation" in res.decisions[0].reason
    assert registry.current_version(led, "power") is None
    assert not registry.versions(led, "power")


def test_same_day_retry_keeps_failure_summary_and_appends_recovery(tmp_path) -> None:
    def broken(cut):
        raise RuntimeError("training failed")

    led = Ledger(tmp_path)
    doms = {"power": EvaluationDomain()}
    first = weekly(led, FixedClock(NOW), doms, {"power": broken}, drift=False)
    original = led.read_bytes(f"models/weekly/{NOW.date()}-summary.json")
    retry = weekly(led, FixedClock(NOW), doms, {"power": good}, drift=False)
    assert not first.ok and retry.ok
    assert led.read_bytes(f"models/weekly/{NOW.date()}-summary.json") == original
    reports = summaries(led)
    assert [s["attempt"] for s in reports] == [2, 1]
    assert [s["ok"] for s in reports] == [True, False]


def test_cli_publishes_failed_decision_before_exiting_nonzero(tmp_path, monkeypatch) -> None:
    from arena.cli import jobs, main
    from arena.ops import wiring
    from arena.ops.weekly import Decision, WeeklyResult

    result = WeeklyResult(NOW.date(), [Decision("power", NOW.date(), NOW.date(), error="failed")])
    published = []
    monkeypatch.setattr(wiring, "weekly_setup", lambda *a: ({}, {}, {}))
    monkeypatch.setattr("arena.ops.weekly.weekly", lambda *a, **kw: result)
    monkeypatch.setattr(jobs, "_sync", lambda *a: "remote")
    monkeypatch.setattr(jobs, "_push", lambda *a: published.append(a[2]))
    res = CliRunner().invoke(main, ["--ledger-dir", str(tmp_path), "weekly", "run", "--push"])
    assert res.exit_code == 1 and "weekly evaluation failed" in res.output
    assert published == ["weekly"]
